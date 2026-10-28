"""Report source Si material surfaces and their dominant bone groups."""
import bpy, json, pathlib, numpy as np, re

ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'tools/model-work/si_ink_mist/source_surface_audit.json'
bpy.ops.wm.open_mainfile(filepath=r'<SOURCE_ROOT>\Rossia\祀.blend')
mesh=bpy.data.objects['祀_mesh']; arm=bpy.data.objects['祀_arm']
groups={g.index:g.name for g in mesh.vertex_groups}
rows=[]
for mi,mat in enumerate(mesh.data.materials):
    vids=[]
    for poly in mesh.data.polygons:
        if poly.material_index==mi:vids.extend(poly.vertices)
    vids=np.unique(vids)
    mass={}
    for vi in vids:
        for g in mesh.data.vertices[int(vi)].groups:
            mass[groups[g.group]]=mass.get(groups[g.group],0)+g.weight
    bones=sorted(mass.items(),key=lambda x:-x[1])[:20]
    points=np.asarray([mesh.matrix_world@mesh.data.vertices[int(v)].co for v in vids],dtype=float) if len(vids) else np.zeros((0,3))
    rows.append({'index':mi,'name':mat.name,'vertices':int(len(vids)),
                 'bounds':np.round([points.min(0),points.max(0)],5).tolist() if len(points) else None,
                 'bones':bones})
OUT.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(rows,ensure_ascii=False,indent=2))
