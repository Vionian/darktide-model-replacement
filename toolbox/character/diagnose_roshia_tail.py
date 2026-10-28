import json
import pathlib

import bpy

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = pathlib.Path(r"<SOURCE_ROOT>\Rossia\洛茜.blend")
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
mesh = bpy.data.objects.get("洛茜_mesh")
armature = bpy.data.objects.get("洛茜_arm")
if mesh is None or armature is None:
    raise RuntimeError("source mesh or armature not found")

group_names = {group.index: group.name for group in mesh.vertex_groups}
tail_names = sorted(name for name in group_names.values() if name.startswith("tail_base_"))
tail_groups = set(tail_names)
tail_vertices = []
for vertex in mesh.data.vertices:
    weight = sum(assignment.weight for assignment in vertex.groups
                 if group_names.get(assignment.group) in tail_groups)
    if weight > 0.05:
        tail_vertices.append({"index": vertex.index, "weight": weight, "co": list(vertex.co)})

records = []
for bone in armature.data.bones:
    if bone.name.startswith("tail_base_"):
        head = armature.matrix_world @ bone.head_local
        tail = armature.matrix_world @ bone.tail_local
        records.append({
            "name": bone.name,
            "parent": bone.parent.name if bone.parent else None,
            "head": list(head),
            "tail": list(tail),
            "length": bone.length,
        })

materials = []
mesh.data.calc_loop_triangles()
for index, material in enumerate(mesh.data.materials):
    triangles = 0
    weighted = 0
    for triangle in mesh.data.loop_triangles:
        if triangle.material_index != index:
            continue
        triangles += 1
        if max(sum(assignment.weight for assignment in mesh.data.vertices[v].groups
                   if group_names.get(assignment.group) in tail_groups)
               for v in triangle.vertices) > 0.2:
            weighted += 1
    materials.append({"index": index, "name": material.name if material else None,
                      "triangles": triangles, "tail_weighted_triangles": weighted})

out = ROOT / "tools" / "model-work" / "roshia" / "tail_diagnostic.json"
out.write_text(json.dumps({"bones": records, "tail_groups": tail_names,
                           "tail_vertices": tail_vertices, "materials": materials},
                          ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"bones": len(records), "groups": len(tail_names),
                  "tail_vertices": len(tail_vertices), "materials": materials},
                 ensure_ascii=False))
