import argparse
import importlib.util
import json
import pathlib
import sys
from collections import Counter, defaultdict

import bpy
from mathutils import Matrix, Vector


ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILDER_PATH = ROOT / "tools" / "model-work" / "build_roshia_native.py"

spec = importlib.util.spec_from_file_location("roshia_builder", BUILDER_PATH)
builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)

parser = argparse.ArgumentParser()
parser.add_argument("--source-blend", type=pathlib.Path, default=builder.SOURCE_BLEND)
parser.add_argument("--template-dir", type=pathlib.Path, default=builder.TEMPLATE)
parser.add_argument(
    "--output",
    type=pathlib.Path,
    default=ROOT / "tools" / "model-work" / "roshia" / "first_build" / "retarget_diagnostics.json",
)
parser.add_argument("--mesh-object", default=builder.MESH_OBJECT_NAME)
parser.add_argument("--armature-object", default=builder.ARMATURE_OBJECT_NAME)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

builder.SOURCE_BLEND = args.source_blend.resolve()
builder.TEMPLATE = args.template_dir.resolve()
builder.MESH_OBJECT_NAME = args.mesh_object
builder.ARMATURE_OBJECT_NAME = args.armature_object
bpy.ops.wm.open_mainfile(filepath=str(builder.SOURCE_BLEND))

from bitsquid.stingray.bones import BonesResourceDT

mesh = bpy.data.objects[builder.MESH_OBJECT_NAME]
armature = bpy.data.objects[builder.ARMATURE_OBJECT_NAME]
mesh.data.calc_loop_triangles()
unit = builder.load_target_unit()
template_bones = BonesResourceDT(
    builder.Cursor(str(builder.TEMPLATE / "qianxia_bones.bones"))
)
node_name_by_hash = {
    bone_hash.ID: name
    for bone_hash, name in zip(template_bones.bones_name_hashes, template_bones.bone_names)
}
node_records = []
world_relation_errors = {"parent_local": 0.0, "local_parent": 0.0}
relation_error_samples = []

def matrix_error(left, right):
    return max(abs(float(left[row][column] - right[row][column]))
               for row in range(4) for column in range(4))

for index, node in enumerate(unit.scene_graph.nodes):
    name = node_name_by_hash.get(node.name.ID, node.name.lookup())
    parent_index = node.parent_index if int(node.parent_type.value) == 1 else None
    parent_name = (
        node_name_by_hash.get(unit.scene_graph.nodes[parent_index].name.ID,
                              unit.scene_graph.nodes[parent_index].name.lookup())
        if parent_index is not None else None
    )
    if parent_index is not None:
        parent_world = unit.scene_graph.nodes[parent_index].world_transform
        parent_local_error = matrix_error(parent_world @ node.local_transform, node.world_transform)
        local_parent_error = matrix_error(node.local_transform @ parent_world, node.world_transform)
        world_relation_errors["parent_local"] = max(
            world_relation_errors["parent_local"],
            parent_local_error,
        )
        world_relation_errors["local_parent"] = max(
            world_relation_errors["local_parent"],
            local_parent_error,
        )
        if name in {"j_spine", "j_spine2", "j_head", "qianxia_hair_021", "qianxia_cloth_129"}:
            relation_error_samples.append({
                "name": name,
                "parent": parent_name,
                "parent_local_error": parent_local_error,
                "local_parent_error": local_parent_error,
                "local_matrix": [[round(float(value), 5) for value in row] for row in node.local_transform],
                "world_matrix": [[round(float(value), 5) for value in row] for row in node.world_transform],
                "parent_world_matrix": [[round(float(value), 5) for value in row] for row in parent_world],
            })
    node_records.append({
        "index": index,
        "name": name,
        "parent_index": parent_index,
        "parent": parent_name,
        "position": [round(float(value), 6) for value in node.world_transform.translation],
        "local_position": [round(float(value), 6) for value in node.local_transform.translation],
    })
bone_targets = builder.source_bone_targets(armature)
group_names = {group.index: group.name for group in mesh.vertex_groups}
dynamic_terms = (
    "hair", "cape", "cloak", "tail", "cloth", "skirt", "manto",
    "髪", "前髪", "横髪", "後髪",
)
dynamic_bones = {
    bone.name for bone in armature.data.bones
    if any(term in bone.name.lower() for term in dynamic_terms)
}
weight_sum = defaultdict(float)
weighted_vertices = defaultdict(int)
for vertex in mesh.data.vertices:
    for assignment in vertex.groups:
        name = group_names.get(assignment.group)
        if name in dynamic_bones:
            weight_sum[name] += float(assignment.weight)
            weighted_vertices[name] += 1

dynamic_targets = Counter()
dynamic_weight_by_target = Counter()
dynamic_records = []
for name in sorted(dynamic_bones):
    target = bone_targets[name]
    if weight_sum[name] > 0:
        dynamic_targets[target] += 1
        dynamic_weight_by_target[target] += weight_sum[name]
        bone = armature.data.bones[name]
        dynamic_records.append({
            "source_bone": name,
            "parent": bone.parent.name if bone.parent else None,
            "mapped_target": target,
            "weighted_vertices": weighted_vertices[name],
            "weight_sum": round(weight_sum[name], 4),
        })

target_names = [node.name.lookup() for node in unit.scene_graph.nodes]
target_dynamic = [
    record["name"] for record in node_records
    for name in (record["name"],)
    if any(term in name.lower() for term in dynamic_terms)
]
materials = []
for index, material in enumerate(mesh.data.materials):
    images = []
    if material and material.use_nodes:
        images = sorted({
            node.image.name
            for node in material.node_tree.nodes
            if node.type == "TEX_IMAGE" and node.image
        })
    materials.append({"slot": index, "name": material.name if material else None, "images": images})

corners = [mesh.matrix_world @ Vector(corner) for corner in mesh.bound_box]
minimum = [min(float(point[i]) for point in corners) for i in range(3)]
maximum = [max(float(point[i]) for point in corners) for i in range(3)]
shape_keys = mesh.data.shape_keys
skin = unit.skins[0]
bind_matrix_errors = {"world_inverse": 0.0, "inverse_world": 0.0}
for palette, node_index in enumerate(skin.node_indices):
    world = unit.scene_graph.nodes[node_index].world_transform
    inverse_bind = skin.inv_bind_matrices[palette]
    bind_matrix_errors["world_inverse"] = max(
        bind_matrix_errors["world_inverse"], matrix_error(world @ inverse_bind, Matrix.Identity(4))
    )
    bind_matrix_errors["inverse_world"] = max(
        bind_matrix_errors["inverse_world"], matrix_error(inverse_bind @ world, Matrix.Identity(4))
    )
report = {
    "source_blend": str(builder.SOURCE_BLEND),
    "mesh_object": mesh.name,
    "armature_object": armature.name,
    "source_mesh": {
        "vertices": len(mesh.data.vertices),
        "triangles": len(mesh.data.loop_triangles),
        "material_slots": len(mesh.data.materials),
        "shape_keys": len(shape_keys.key_blocks) if shape_keys else 0,
        "bounds_min": minimum,
        "bounds_max": maximum,
    },
    "source_bones": len(armature.data.bones),
    "target_skeleton": {
        "scene_nodes": len(unit.scene_graph.nodes),
        "skin_joints": len(unit.skins[0].node_indices),
        "dynamic_named_nodes": target_dynamic,
        "dynamic_nodes": [record for record in node_records
                          if any(term in record["name"].lower() for term in dynamic_terms)],
        "world_relation_errors": world_relation_errors,
        "world_relation_error_samples": relation_error_samples,
        "bind_matrix_errors": bind_matrix_errors,
    },
    "secondary_motion": {
        "source_dynamic_named_bones": len(dynamic_bones),
        "weighted_source_dynamic_bones": len(dynamic_records),
        "mapped_target_bone_counts": dict(dynamic_targets),
        "mapped_weight_sum_by_target": {
            name: round(value, 3) for name, value in dynamic_weight_by_target.items()
        },
        "bones": dynamic_records,
    },
    "material_slots": materials,
}
output = args.output.resolve()
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("ROSHIA_DIAGNOSTICS " + json.dumps({
    "output": str(output),
    "source_dynamic_bones": len(dynamic_bones),
    "weighted_dynamic_bones": len(dynamic_records),
    "target_dynamic_nodes": len(target_dynamic),
    "mapped_weight_sum_by_target": report["secondary_motion"]["mapped_weight_sum_by_target"],
}, ensure_ascii=False))
