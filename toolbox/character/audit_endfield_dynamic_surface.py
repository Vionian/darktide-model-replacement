"""Report dynamic-bone influence by material and source height.

This is deliberately source-side: it helps distinguish a missing surface caused
by a bad helper-bone assignment from a native renderer or visibility issue.
"""
import argparse
import collections
import json
import pathlib
import sys

import bpy

parser = argparse.ArgumentParser()
parser.add_argument("--source-blend", type=pathlib.Path, required=True)
parser.add_argument("--mapping", type=pathlib.Path, required=True)
parser.add_argument("--mesh", required=True)
parser.add_argument("--output", type=pathlib.Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])

bpy.ops.wm.open_mainfile(filepath=str(args.source_blend.resolve()))
mesh = bpy.data.objects.get(args.mesh)
if mesh is None:
    raise RuntimeError(f"missing mesh object: {args.mesh}")
mapping = json.loads(args.mapping.read_text(encoding="utf-8-sig"))
dynamic = {row["source_bone"] for row in mapping.get("runtime_bones", [])}
group_names = {group.index: group.name for group in mesh.vertex_groups}
material_names = [slot.material.name if slot.material else f"slot_{i}" for i, slot in enumerate(mesh.material_slots)]

rows = {name: {"polygons": 0, "dynamic_polygons": 0, "dynamic_vertices": 0,
               "vertices": 0, "dynamic_weight_sum": 0.0, "zmin": None, "zmax": None}
        for name in material_names}
bands = collections.defaultdict(lambda: {"vertices": 0, "dynamic_vertices": 0, "weight_sum": 0.0})
group_stats = collections.defaultdict(lambda: {"weight_sum": 0.0, "vertices": 0, "zmin": None, "zmax": None})

vertex_dynamic = {}
for vertex in mesh.data.vertices:
    total = 0.0
    for assignment in vertex.groups:
        group = group_names.get(assignment.group, "")
        if group in dynamic:
            total += float(assignment.weight)
            stat = group_stats[group]
            stat["weight_sum"] += float(assignment.weight)
            stat["vertices"] += 1
            z = float((mesh.matrix_world @ vertex.co).z)
            stat["zmin"] = z if stat["zmin"] is None else min(stat["zmin"], z)
            stat["zmax"] = z if stat["zmax"] is None else max(stat["zmax"], z)
    vertex_dynamic[vertex.index] = total
    z = float((mesh.matrix_world @ vertex.co).z)
    band = str(int(z * 10) / 10)
    bands[band]["vertices"] += 1
    bands[band]["dynamic_vertices"] += int(total > 0.5)
    bands[band]["weight_sum"] += total

for polygon in mesh.data.polygons:
    slot = material_names[polygon.material_index] if polygon.material_index < len(material_names) else f"slot_{polygon.material_index}"
    row = rows.setdefault(slot, {"polygons": 0, "dynamic_polygons": 0, "dynamic_vertices": 0,
                                 "vertices": 0, "dynamic_weight_sum": 0.0, "zmin": None, "zmax": None})
    weights = [vertex_dynamic[v] for v in polygon.vertices]
    zs = [float((mesh.matrix_world @ mesh.data.vertices[v].co).z) for v in polygon.vertices]
    row["polygons"] += 1
    row["vertices"] += len(weights)
    row["dynamic_vertices"] += sum(w > 0.5 for w in weights)
    row["dynamic_weight_sum"] += sum(weights) / max(1, len(weights))
    row["dynamic_polygons"] += int(sum(w > 0.5 for w in weights) == len(weights))
    row["zmin"] = min(zs) if row["zmin"] is None else min(row["zmin"], min(zs))
    row["zmax"] = max(zs) if row["zmax"] is None else max(row["zmax"], max(zs))

for row in rows.values():
    row["dynamic_polygon_fraction"] = row["dynamic_polygons"] / max(1, row["polygons"])
    row["dynamic_vertex_fraction"] = row["dynamic_vertices"] / max(1, row["vertices"])
    row["mean_dynamic_weight_per_polygon"] = row["dynamic_weight_sum"] / max(1, row["polygons"])

report = {"source_blend": str(args.source_blend), "mesh": mesh.name,
          "vertices": len(mesh.data.vertices), "polygons": len(mesh.data.polygons),
          "dynamic_source_bones": len(dynamic), "materials": rows,
          "height_bands": dict(sorted(bands.items(), key=lambda item: float(item[0]))),
          "dynamic_groups": dict(sorted(group_stats.items(), key=lambda item: -item[1]["weight_sum"]))}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"mesh": mesh.name, "dynamic_source_bones": len(dynamic),
                  "materials": {k: {"polygon_fraction": round(v["dynamic_polygon_fraction"], 4),
                                     "vertex_fraction": round(v["dynamic_vertex_fraction"], 4),
                                     "zmin": v["zmin"], "zmax": v["zmax"]}
                                 for k, v in rows.items()}}, ensure_ascii=False))
