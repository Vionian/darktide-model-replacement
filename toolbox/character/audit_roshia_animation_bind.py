"""Offline bind/link regression audit. Run with Blender --background --python."""
import importlib.util
import json
import pathlib
import sys
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("builder", HERE / "build_roshia_native.py")
b = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = b
spec.loader.exec_module(b)
template = b.load_target_unit()
bone_names = b.BonesResourceDT(b.Cursor(str(b.TEMPLATE / "qianxia_bones.bones")))
lookup = b.named_node_map(template, bone_names)
names = {index: name for name, index in lookup.items()}
report = {}
report["reference_rigs"] = {}
for asset in ("daniya_blue", "aimisi"):
    folder = b.ROOT / "Custom" / asset
    reference = b.unit_dt.UnitResourceDT(b.Cursor(str(folder / (asset + ".unit"))))
    bones = b.BonesResourceDT(b.Cursor(str(folder / (asset + "_bones.bones"))))
    reference_lookup = b.named_node_map(reference, bones)
    common = [name for name in lookup if name.startswith("j_") and name in reference_lookup]
    errors = {name: b.matrix_max_error(template.scene_graph.nodes[lookup[name]].world_transform,
                                      reference.scene_graph.nodes[reference_lookup[name]].world_transform)
              for name in common}
    report["reference_rigs"][asset] = {"common_named_nodes": len(common),
                                       "max_world_matrix_error": max(errors.values()),
                                       "nodes_over_1e_4": {name: error for name, error in errors.items() if error > 1e-4}}
for candidate in ("deform_fix_candidate", "animation_bind_candidate", "surface_uv_candidate"):
    report[candidate] = {}
    for asset in ("roshia", "roshia_arms"):
        folder = HERE / "roshia" / candidate / "Custom" / asset
        unit = b.unit_dt.UnitResourceDT(b.Cursor(str(folder / (asset + ".unit"))))
        cache = {}
        def linked_world(index):
            if index in cache:
                return cache[index]
            node = unit.scene_graph.nodes[index]
            if names.get(index, "").startswith("j_"):
                world = template.scene_graph.nodes[index].world_transform.copy()
            else:
                world = (linked_world(node.parent_index) @ node.local_transform
                         if node.parent_type == b.ParentType.INTERNAL else node.local_transform)
            cache[index] = world
            return world
        skin = unit.skins[0]
        matrices = np.asarray([linked_world(index) @ inverse
                               for index, inverse in zip(skin.node_indices, skin.inv_bind_matrices)])
        deltas = []
        for geo in unit.mesh_geometries:
            channels = {c.component.name: c for c in geo.channels}
            pc = channels["POSITION"]
            positions = geo.streams[pc.stream].get_positions(pc).astype(np.float32)
            # Builder's verified stream layout: half-float weights, byte palette.
            weights = np.frombuffer(geo.streams[4].vertex_data, dtype="<f2").reshape((-1, 4)).astype(np.float32)
            joints = np.frombuffer(geo.streams[5].vertex_data, dtype=np.uint8).reshape((-1, 4))
            weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-8)
            blended = (matrices[joints] * weights[:, :, None, None]).sum(axis=1)
            posed = np.einsum("nij,nj->ni", blended[:, :3, :3], positions) + blended[:, :3, 3]
            deltas.extend(np.linalg.norm(posed - positions, axis=1).tolist())
        native_error = max(b.matrix_max_error(unit.scene_graph.nodes[i].world_transform,
                                              template.scene_graph.nodes[i].world_transform)
                           for i, name in names.items() if name.startswith("j_"))
        entry = {"named_node_max_matrix_error": native_error,
                 "simulated_link_max_vertex_delta_m": max(deltas),
                 "simulated_link_mean_vertex_delta_m": float(np.mean(deltas))}
        if candidate in ("animation_bind_candidate", "surface_uv_candidate"):
            assert native_error < 2e-5, entry
            assert max(deltas) < 2e-5, entry
        report[candidate][asset] = entry
out = HERE / "roshia/surface_uv_candidate/animation_bind_audit.json"
out.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("ANIMATION_BIND_AUDIT " + json.dumps(report))
