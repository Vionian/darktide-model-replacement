"""Inspect source UV/alpha and tail coverage, run with Blender."""
import importlib.util
import json
import pathlib
import sys
import bpy
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("builder", HERE / "build_roshia_native.py")
b = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = b
spec.loader.exec_module(b)
bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
mesh = bpy.data.objects[b.MESH_OBJECT_NAME]
mesh.data.calc_loop_triangles()
groups = {g.index: g.name for g in mesh.vertex_groups}
tail_vertices = {v.index for v in mesh.data.vertices if any(
    groups[a.group].startswith("tail_base_") and a.weight > 0.05 for a in v.groups)}
report = {}
for i, mat in enumerate(mesh.data.materials):
    triangles = [t for t in mesh.data.loop_triangles if t.material_index == i]
    uv = np.asarray([mesh.data.uv_layers.active.data[l].uv[:]
                     for t in triangles for l in t.loops], dtype=np.float32)
    image = b.image_pixels_for(mat)
    colors = b.sample_image(image, uv)
    flipped = uv.copy()
    flipped[:, 1] = 1 - flipped[:, 1]
    flipped_colors = b.sample_image(image, flipped)
    tail_triangles = [t for t in triangles if any(v in tail_vertices for v in t.vertices)]
    tail_uv = np.asarray([mesh.data.uv_layers.active.data[l].uv[:]
                          for t in tail_triangles for l in t.loops], dtype=np.float32).reshape((-1, 2))
    entry = {"name": mat.name, "triangles": len(triangles), "texture_size": image[:2],
             "alpha_material": b.material_is_alpha(i, mat.name),
             "tail_triangles": len(tail_triangles),
             "vertical_uv_flip_mean_rgb_delta": float(np.abs(colors[:, :3] - flipped_colors[:, :3]).mean())}
    if len(tail_uv):
        alpha = b.sample_image(image, tail_uv)[:, 3]
        tail_uv[:, 1] = 1 - tail_uv[:, 1]
        wrong_alpha = b.sample_image(image, tail_uv)[:, 3]
        entry.update(tail_source_alpha_visible_fraction=float((alpha > 0.5).mean()),
                     tail_wrong_origin_alpha_visible_fraction=float((wrong_alpha > 0.5).mean()))
    report[i] = entry
out = HERE / "roshia/surface_fix_candidate"
out.mkdir(parents=True, exist_ok=True)
(out / "source_surface_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("SURFACE_AUDIT " + json.dumps(report, ensure_ascii=False))
