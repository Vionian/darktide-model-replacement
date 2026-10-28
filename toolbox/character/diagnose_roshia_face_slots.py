import importlib.util
import json
import pathlib
import sys

import bpy
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("roshia_builder", HERE / "build_roshia_native.py")
builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)

bpy.ops.wm.open_mainfile(filepath=str(builder.SOURCE_BLEND))
mesh = bpy.data.objects[builder.MESH_OBJECT_NAME]
mesh.data.calc_loop_triangles()
uv_layer = mesh.data.uv_layers.active.data
out = {}
for index, material in enumerate(mesh.data.materials):
    triangles = [triangle for triangle in mesh.data.loop_triangles
                 if triangle.material_index == index]
    if not triangles:
        continue
    vertices = sorted({loop.vertex_index for triangle in triangles
                       for loop in (mesh.data.loops[i] for i in triangle.loops)})
    positions = np.asarray([(mesh.matrix_world @ mesh.data.vertices[v].co)[:] for v in vertices])
    uvs = np.asarray([uv_layer[loop_index].uv[:]
                      for triangle in triangles for loop_index in triangle.loops], dtype=np.float32)
    image = builder.image_pixels_for(material)
    sampled = builder.sample_image(image, uvs)
    out[index] = {
        "name": material.name,
        "triangles": len(triangles),
        "vertices": len(vertices),
        "bounds": {
            "min": positions.min(axis=0).tolist(),
            "max": positions.max(axis=0).tolist(),
        },
        "uv_min": uvs.min(axis=0).tolist(),
        "uv_max": uvs.max(axis=0).tolist(),
        "sample_rgb_mean": sampled[:, :3].mean(axis=0).tolist(),
        "sample_alpha_min": float(sampled[:, 3].min()),
        "sample_alpha_max": float(sampled[:, 3].max()),
        "sample_alpha_mean": float(sampled[:, 3].mean()),
    }
path = HERE / "roshia" / "face_slot_diagnostic.json"
path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("FACE_SLOT_DIAGNOSTIC " + json.dumps(out, ensure_ascii=False))
