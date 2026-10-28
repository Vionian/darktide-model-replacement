"""Offline reference rig comparison; run using Blender --background --python."""
import importlib.util
import pathlib
import sys
import json
import struct
import bpy
from mathutils import Matrix

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("builder", HERE / "build_roshia_native.py")
b = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = b
spec.loader.exec_module(b)
results = {}
names = ("j_hips", "j_spine", "j_spine2", "j_neck", "j_head", "j_leftarm", "j_leftforearm", "j_lefthand", "j_leftupleg", "j_leftleg", "j_leftfoot", "j_lefttoebase")
original_template = b.TEMPLATE
for label, folder, asset in [(name, b.ROOT / "Custom" / name, name) for name in (
        "qianxia", "qianxia_arms", "daniya_blue", "daniya_blue_arms", "aimisi", "aimisi_arms", "roshia", "roshia_arms")
    ] + [("roshia_fixed", HERE / "roshia/trs_fix_candidate/Custom/roshia", "roshia"),
         ("roshia_arms_fixed", HERE / "roshia/trs_fix_candidate/Custom/roshia_arms", "roshia_arms")]:
    b.TEMPLATE = folder
    unit = b.unit_dt.UnitResourceDT(b.Cursor(str(folder / (asset + ".unit"))))
    bones = b.BonesResourceDT(b.Cursor(str(folder / (asset + "_bones.bones"))))
    lookup = b.named_node_map(unit, bones)
    info = b.read_unit_offsets(b.TEMPLATE / (asset + ".unit"))
    results[label] = {}
    print("SKIN", label, [(len(s.node_indices), [len(v) for v in s.matrix_index_sets]) for s in unit.skins])
    print("FORWARD_PARENTS", label, [(i,n.parent_index) for i,n in enumerate(unit.scene_graph.nodes) if n.parent_type == b.ParentType.INTERNAL and n.parent_index>=i])
    for name in names:
        i = lookup.get(name)
        if i is None:
            continue
        node = unit.scene_graph.nodes[i]
        results[label][name] = {"index": i, "parent": node.parent_index,
            "world": [list(row) for row in node.world_transform],
            "local": [list(row) for row in node.local_transform],
            "raw_position": struct.unpack_from("<3f", info["raw"], info["scene_graph_start"] + 4 + i*60+36),
            "expected_local_position": list((unit.scene_graph.nodes[node.parent_index].world_transform.inverted() @ node.world_transform).translation)}
b.TEMPLATE = original_template
bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
arm = bpy.data.objects[b.ARMATURE_OBJECT_NAME]
mesh = bpy.data.objects[b.MESH_OBJECT_NAME]
group_names = {group.index: group.name for group in mesh.vertex_groups}
hand_stats = {}
for bone in arm.data.bones:
    if any(term in bone.name for term in ("FingerTop", "Hand_ty", "hand_base")):
        hand_stats[bone.name] = {"parent": bone.parent.name if bone.parent else None,
                               "head": list(b.source_coordinate3() @ (arm.matrix_world @ bone.head_local)),
                               "count": 0, "dominant": 0, "weight_sum": 0}
for vertex in mesh.data.vertices:
    groups = [assignment for assignment in vertex.groups if assignment.weight>1e-5]
    dominant = max(groups, key=lambda assignment: assignment.weight).group if groups else None
    for assignment in groups:
        name = group_names[assignment.group]
        if name in hand_stats:
            hand_stats[name]["count"] += 1
            hand_stats[name]["weight_sum"] += assignment.weight
            hand_stats[name]["dominant"] += int(assignment.group == dominant)
results["hand_helpers"] = hand_stats
results["source"] = {}
for name in ("腰", "上半身", "上半身2", "首", "頭", "左腕", "左ひじ", "左手首", "左足", "左ひざ", "左足首", "左つま先"):
    bone = arm.data.bones.get(name)
    if bone:
        results["source"][name] = {"head": list(b.source_coordinate3() @ (arm.matrix_world @ bone.head_local)),
            "tail": list(b.source_coordinate3() @ (arm.matrix_world @ bone.tail_local))}
(HERE / "roshia" / "rig_comparison.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
for asset, entries in results.items():
    if asset == "hand_helpers":
        continue
    print("RIG", asset)
    for name, entry in entries.items():
        print(name, [round(v,4) for v in (entry.get("head") or [row[3] for row in entry["world"][:3]])])
