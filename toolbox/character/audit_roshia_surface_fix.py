"""Independent compiled-resource comparison and surface coverage checks.

Run with Blender --background --python-exit-code 1 --python this_file.
"""
import importlib.util
import json
import pathlib
import struct
import sys
import bpy
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("builder", HERE / "build_roshia_native.py")
b = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = b
spec.loader.exec_module(b)
from read_native_texture import read_native_top_mip
from inspect_darktide_textures import parse_material_stream

out = HERE / "roshia/surface_uv_candidate"
old_root = HERE / "roshia/animation_bind_candidate/Custom"
new_root = out / "Custom"
codec = b.Oodle(b.OODLE_DLL)
report = {"assets": {}, "textures": {}, "surface_coverage": {}}
for asset in ("roshia", "roshia_arms"):
    folders = [root / asset for root in (old_root, new_root)]
    old, new = [b.unit_dt.UnitResourceDT(b.Cursor(str(folder / (asset + ".unit")))) for folder in folders]
    assert len(old.mesh_geometries) == len(new.mesh_geometries) == 31
    max_v_error, triangles = 0.0, 0
    for before, after in zip(old.mesh_geometries, new.mesh_geometries):
        assert before.index_stream.data == after.index_stream.data
        for index in (0, 1, 2, 4, 5):
            assert before.streams[index].vertex_data == after.streams[index].vertex_data, (asset, index)
        a, z = [np.frombuffer(g.streams[3].vertex_data, dtype="<f2").reshape((-1, 2)).astype(np.float32) for g in (before, after)]
        assert np.array_equal(a[:, 0], z[:, 0])
        err = float(np.abs(z[:, 1] - (1 - a[:, 1])).max())
        assert err <= 0.001, err  # two independent float16 quantizations
        max_v_error = max(max_v_error, err)
        triangles += after.index_stream.index_count // 3
    assert old.skins[0].node_indices == new.skins[0].node_indices
    for a, z in zip(old.scene_graph.nodes, new.scene_graph.nodes):
        assert a.parent_index == z.parent_index and a.parent_type == z.parent_type
        assert b.matrix_max_error(a.local_transform, z.local_transform) == 0
        assert b.matrix_max_error(a.world_transform, z.world_transform) == 0
    for a, z in zip(old.skins[0].inv_bind_matrices, new.skins[0].inv_bind_matrices):
        assert b.matrix_max_error(a, z) == 0
    assert [(x.ID, y.ID) for x, y in old.materials] == [(x.ID, y.ID) for x, y in new.materials]
    manifest = json.loads((folders[1] / "build.json").read_text(encoding="utf-8"))
    texture_ids = {}
    for entry in manifest["artifacts"]:
        path = folders[1] / entry["path"]
        assert path.stat().st_size == entry["size"]
        if entry["role"] == "primary" and entry["resource"]["type"] == "texture":
            texture_ids[f"0x{b.hash64(entry['resource']['name']):016x}"] = path.name
            decoded, meta = read_native_top_mip(path, codec)
            original = (folders[1] / "source_textures/dds" / path.with_suffix(".dds").name).read_bytes()
            assert decoded[148:] == original[148:len(decoded)]
            meta["largest_mip_matches_encoder"] = True
            report["textures"][path.name] = meta
    for path in folders[1].glob("*.material"):
        raw = path.read_bytes()
        stream = folders[1] / raw[38:68].split(b"\0", 1)[0].decode()
        for ref in parse_material_stream(stream.read_bytes()):
            assert ref["resource_hash"] in texture_ids, (path, ref)
    report["assets"][asset] = {"triangles": triangles, "geometry_and_rig_unchanged_except_uv": True,
        "u_unchanged": True, "max_v_flip_quantization_error": max_v_error, "material_texture_references_resolve": True}

# All exported source material counts must survive in the compiled unit.
bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
mesh = bpy.data.objects[b.MESH_OBJECT_NAME]
mesh.data.calc_loop_triangles()
groups = {g.index: g.name for g in mesh.vertex_groups}
tail_vertices = {v.index for v in mesh.data.vertices if any(
    groups[g.group].startswith("tail_base_") and g.weight > 0.05 for g in v.groups)}
body = b.unit_dt.UnitResourceDT(b.Cursor(str(new_root / "roshia/roshia.unit")))
slots = {slot.ID: resource.ID for slot, resource in body.materials}
runtime = json.loads((new_root / "roshia_jiggle_bones.json").read_text(encoding="utf-8"))["runtime_bones"]
bones = b.BonesResourceDT(b.Cursor(str(new_root / "roshia/roshia_bones.bones")))
lookup = b.named_node_map(body, bones)
tail_records = [r for r in runtime if r["group"] == "tail"]
tail_nodes = {lookup[r["node"]] for r in tail_records}
tail_palette = [p for p, n in enumerate(body.skins[0].node_indices) if n in tail_nodes]
tail_exported = 0
for geo in body.mesh_geometries:
    weights = np.frombuffer(geo.streams[4].vertex_data, dtype="<f2").reshape((-1, 4))
    joints = np.frombuffer(geo.streams[5].vertex_data, dtype=np.uint8).reshape((-1, 4))
    tw = np.where(np.isin(joints, tail_palette), weights, 0).sum(axis=1)
    tail_exported += int((tw.reshape((-1, 3)) > 0.05).any(axis=1).sum())
for index, mat in enumerate(mesh.data.materials):
    if any(t.casefold() in mat.name.casefold() for t in b.SKIP_MATERIAL_NAMES):
        continue
    triangles = [t for t in mesh.data.loop_triangles if t.material_index == index]
    resource = b.hash64(f"content/mods/roshia/roshia_material_{index}")
    count = sum(g.index_stream.index_count // 3 for g in body.mesh_geometries if slots[g.materials[0].ID] == resource)
    assert count == len(triangles), (mat.name, count, len(triangles))
    report["surface_coverage"][mat.name] = {"source_triangles": len(triangles), "compiled_triangles": count,
        "tail_triangles": sum(any(v in tail_vertices for v in t.vertices) for t in triangles)}
source_tail_count = sum(v["tail_triangles"] for v in report["surface_coverage"].values())
assert source_tail_count == tail_exported, (source_tail_count, tail_exported)
for record in tail_records:
    n = body.scene_graph.nodes[lookup[record["node"]]]
    assert n.parent_index == lookup[record["parent"]]
assert len(tail_records) == 21
assert not any(r["source_bone"].startswith(("shawl_base_", "hat_base_")) for r in runtime)
report["tail"] = {"source_triangles": source_tail_count, "compiled_triangles": tail_exported,
                  "runtime_chain_nodes": len(tail_records), "parent_links_valid": True}
report["mesh_visibility"] = {
    "meshes": [{"geometry": m.geometry_index, "skin": m.skin_index, "node": m.node_index,
                 "flags": [m.unk4, m.unk5, m.unk6]} for m in body.meshes],
    "lods": [{"steps": [{"range": s.visible_height_range, "meshes": s.meshes} for s in lod.steps],
              "stream_mesh_order": lod.stream_mesh_order} for lod in body.lod_objects],
    "visibility_groups": [(str(name.ID), indices) for name, indices in body.visibility_groups],
}
(out / "surface_resource_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("SURFACE_RESOURCE_AUDIT_OK " + json.dumps({"assets": report["assets"], "tail": report["tail"],
    "textures_checked": len(report["textures"])}))
