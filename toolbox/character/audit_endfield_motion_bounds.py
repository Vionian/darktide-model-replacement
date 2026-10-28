"""Audit whether authored/runtime poses move skinned chunks outside static bounds."""
import argparse
import importlib.util
import json
import pathlib
import sys

import bpy
import numpy as np
from mathutils import Matrix

ROOT = pathlib.Path(__file__).resolve().parents[2]
builder_path = ROOT / "tools" / "model-work" / "build_roshia_native.py"
sys.path.insert(0, str(builder_path.parent))
spec = importlib.util.spec_from_file_location("roshia_builder", builder_path)
b = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = b
spec.loader.exec_module(b)

parser = argparse.ArgumentParser()
parser.add_argument("--assets-root", type=pathlib.Path, default=ROOT / "Custom")
parser.add_argument("--pose-dir", type=pathlib.Path, default=ROOT / "tools/model-work/endfield_batch/perlica")
parser.add_argument("--models", nargs="*", default=[])
parser.add_argument("--output", type=pathlib.Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

models = args.models or sorted(p.name for p in args.assets_root.iterdir()
                               if p.is_dir() and (p / f"{p.name}.unit").is_file()
                               and not p.name.endswith("_arms"))

reports = {}
for model in models:
    unit_path = args.assets_root / model / f"{model}.unit"
    if not unit_path.is_file():
        continue
    unit = b.unit_dt.UnitResourceDT(b.Cursor(str(unit_path)))
    skin = unit.skins[0]
    geom_rows = []
    for i, (geo, mesh_obj) in enumerate(zip(unit.mesh_geometries, unit.meshes)):
        channel = next(c for c in geo.channels if c.component.name == "POSITION")
        positions = geo.streams[channel.stream].get_positions(channel).astype(np.float64)
        indices = np.frombuffer(geo.streams[5].vertex_data, dtype=np.uint8).reshape(-1, 4)
        weights = np.frombuffer(geo.streams[4].vertex_data, dtype="<f2").reshape(-1, 4).astype(np.float64)
        weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-12)
        bounds = geo.bounding_volume
        center = np.array((bounds.unk1, bounds.unk2, bounds.unk3), dtype=np.float64)
        radius = float(bounds.unk4)
        minimum = positions.min(axis=0)
        maximum = positions.max(axis=0)
        # Bounds are serialized in the mesh node's local space. Runtime
        # fixtures also contain the actor/world transform, so remove the mesh
        # node transform before testing to avoid treating actor movement as
        # missing geometry.
        geom_rows.append({"index": i, "positions": positions, "indices": indices,
                          "weights": weights, "center": center, "radius": radius,
                          "minimum": minimum, "maximum": maximum,
                          "mesh_node": int(mesh_obj.node_index),
                          "slot": int(geo.slot_id) if hasattr(geo, "slot_id") else None,
                          "vertices": int(len(positions))})

    model_report = {"unit": str(unit_path), "geometries": len(geom_rows), "poses": {}}
    model_pose_dir = args.pose_dir / model
    if not model_pose_dir.is_dir():
        model_pose_dir = args.pose_dir
    pose_files = sorted(model_pose_dir.glob("body_*_pose.json"))
    if not pose_files:
        model_report["pose_fixture_error"] = f"No body poses in {model_pose_dir}"
        reports[model] = model_report
        continue
    for pose_file in pose_files:
        data = json.loads(pose_file.read_text(encoding="utf-8"))
        worlds = [Matrix(m) for m in data["worlds"]]
        if max(skin.node_indices, default=0) >= len(worlds):
            model_report["poses"][pose_file.stem] = {"error": "pose node count mismatch"}
            continue
        palette = np.asarray([np.asarray(worlds[node]) @ np.asarray(inv)
                              for node, inv in zip(skin.node_indices, skin.inv_bind_matrices)], dtype=np.float64)
        worst = {"max_aabb_overrun_m": 0.0, "max_sphere_overrun_m": 0.0,
                 "vertices_outside_aabb": 0, "vertices_outside_sphere": 0, "total_vertices": 0,
                 "worst_geometry": None, "max_displacement_m": 0.0,
                 "flipped_triangles": 0, "total_triangles": 0,
                 "worst_flip_geometry": None, "max_flip_fraction": 0.0}
        per_geometry = []
        for g in geom_rows:
            mats = palette[g["indices"]]
            blended = (mats * g["weights"][:, :, None, None]).sum(axis=1)
            posed_world = np.einsum("nij,nj->ni", blended[:, :3, :3], g["positions"]) + blended[:, :3, 3]
            mesh_world = np.asarray(worlds[g["mesh_node"]], dtype=np.float64)
            posed = np.einsum("ij,nj->ni", np.linalg.inv(mesh_world[:3, :3]),
                              posed_world - mesh_world[:3, 3])
            outside = np.maximum(np.maximum(g["minimum"] - posed, posed - g["maximum"]), 0.0)
            aabb_overrun = np.linalg.norm(outside, axis=1)
            sphere_overrun = np.maximum(np.linalg.norm(posed - g["center"], axis=1) - g["radius"], 0.0)
            displacement = np.linalg.norm(posed - g["positions"], axis=1)
            rest_tri = g["positions"].reshape(-1, 3, 3)
            posed_tri = posed.reshape(-1, 3, 3)
            rest_normal = np.cross(rest_tri[:, 1] - rest_tri[:, 0], rest_tri[:, 2] - rest_tri[:, 0])
            posed_normal = np.cross(posed_tri[:, 1] - posed_tri[:, 0], posed_tri[:, 2] - posed_tri[:, 0])
            valid_tri = (np.linalg.norm(rest_normal, axis=1) > 1e-10) & (np.linalg.norm(posed_normal, axis=1) > 1e-10)
            flipped = valid_tri & (np.sum(rest_normal * posed_normal, axis=1) < 0.0)
            flip_fraction = float(np.count_nonzero(flipped) / max(1, np.count_nonzero(valid_tri)))
            row = {"geometry": g["index"], "vertices": g["vertices"],
                   "aabb_outside": int(np.count_nonzero(aabb_overrun > 1e-4)),
                   "aabb_overrun_max_m": float(aabb_overrun.max(initial=0)),
                   "sphere_outside": int(np.count_nonzero(sphere_overrun > 1e-4)),
                   "sphere_overrun_max_m": float(sphere_overrun.max(initial=0)),
                   "max_displacement_m": float(displacement.max(initial=0)),
                   "flipped_triangles": int(np.count_nonzero(flipped)),
                   "total_triangles": int(len(valid_tri)),
                   "flip_fraction": flip_fraction}
            per_geometry.append(row)
            if row["aabb_overrun_max_m"] > worst["max_aabb_overrun_m"]:
                worst["max_aabb_overrun_m"] = row["aabb_overrun_max_m"]
                worst["worst_geometry"] = row["geometry"]
            worst["max_sphere_overrun_m"] = max(worst["max_sphere_overrun_m"], row["sphere_overrun_max_m"])
            worst["vertices_outside_aabb"] += row["aabb_outside"]
            worst["vertices_outside_sphere"] += row["sphere_outside"]
            worst["total_vertices"] += row["vertices"]
            worst["max_displacement_m"] = max(worst["max_displacement_m"], row["max_displacement_m"])
            worst["flipped_triangles"] += row["flipped_triangles"]
            worst["total_triangles"] += row["total_triangles"]
            if row["flip_fraction"] > worst["max_flip_fraction"]:
                worst["max_flip_fraction"] = row["flip_fraction"]
                worst["worst_flip_geometry"] = row["geometry"]
        model_report["poses"][pose_file.stem] = {
            "case": data.get("case"), "synthetic": data.get("synthetic"),
            "description": data.get("description"), "summary": worst,
            "top_aabb_overrun_geometries": sorted(per_geometry, key=lambda x:x["aabb_overrun_max_m"], reverse=True)[:6],
            "top_sphere_overrun_geometries": sorted(per_geometry, key=lambda x:x["sphere_overrun_max_m"], reverse=True)[:6],
            "top_flip_geometries": sorted(per_geometry, key=lambda x:x["flip_fraction"], reverse=True)[:6],
        }
    reports[model] = model_report

args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(reports, indent=2), encoding="utf-8")
print(json.dumps({k:{pose:v["summary"] for pose,v in row["poses"].items()} for k,row in reports.items()}, indent=2))
