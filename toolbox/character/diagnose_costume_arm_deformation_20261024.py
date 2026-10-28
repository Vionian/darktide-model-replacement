"""Read prepared source and measured builder positions; do not modify assets."""
import sys,json,re
from pathlib import Path
import bpy,numpy as np
HERE=Path(__file__).resolve().parent
tag=sys.argv[sys.argv.index('--')+1]
folder=HERE/'skins_20261023'/tag
ref=json.loads((HERE/'skins_20261023/references/endministrator_f/source.json').read_text(encoding='utf8'))
blend=list((folder/'native').glob('*_original_hand_MMR.blend'))
assert len(blend)==1,blend
bpy.ops.wm.open_mainfile(filepath=str(blend[0]))
mesh=bpy.data.objects[ref['mesh']];arm=bpy.data.objects[ref['armature']]
source=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices])
fitted=np.load(HERE/'hand_repair_20261024'/tag/'body_upper-body/roshia_builder_retargeted_positions.npy')
assert len(source)==len(fitted)
labels={g.index:g.name for g in mesh.vertex_groups}
rows=[]
for suffix in ('.L','.R'):
    joints={n:np.array(arm.matrix_world@arm.data.bones[n+suffix].head_local)for n in ('腕','ひじ','手首')}
    print('BONES',suffix,{n:p.tolist()for n,p in joints.items()},flush=True)
    axis=joints['手首']-joints['ひじ'];length=np.linalg.norm(axis);axis/=length
    t=(source-joints['ひじ'])@axis/length
    radial=np.linalg.norm((source-joints['ひじ'])-np.outer(t*length,axis),axis=1)
    ids=np.flatnonzero((t>-.15)&(t<1)&(radial<.09))
    material_by_vi={i:set()for i in ids}
    for poly in mesh.data.polygons:
        for vi in poly.vertices:
            if vi in material_by_vi:material_by_vi[vi].add(mesh.data.materials[poly.material_index].name)
    samples=[]
    for lo,hi in zip(np.arange(-.1,1,.1),np.arange(0,1.1,.1)):
        selected=[int(i)for i in ids if lo<=t[i]<hi]
        groups={}
        for i in selected:
            for g in mesh.data.vertices[i].groups:
                name=labels[g.group];groups[name]=groups.get(name,0)+g.weight/max(1,len(selected))
        samples.append(dict(range=[float(lo),float(hi)],vertices=len(selected),average_weights=sorted(groups.items(),key=lambda p:-p[1])[:6]))
    for i in ids[::max(1,len(ids)//20)]:
        rows.append(dict(side=suffix,vertex=int(i),axial=float(t[i]),radial_mm=float(radial[i]*1000),source=source[i].tolist(),fitted=fitted[i].tolist(),materials=list(material_by_vi[i]),weights=[(labels[g.group],g.weight)for g in mesh.data.vertices[i].groups if g.weight>.001]))
    print('AXIAL_WEIGHTS',suffix,json.dumps(samples,ensure_ascii=False),flush=True)
mesh.data.calc_loop_triangles()
tri=np.array([f.vertices[:]for f in mesh.data.loop_triangles])
edges=np.unique(np.sort(np.concatenate((tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]])),axis=1),axis=0)
a=np.linalg.norm(source[edges[:,0]]-source[edges[:,1]],axis=1)*ref['scale'];z=np.linalg.norm(fitted[edges[:,0]]-fitted[edges[:,1]],axis=1)
selected=(a>.0005)&(z>a*5)
worst=[]
for k in np.flatnonzero(selected)[np.argsort((z/np.maximum(a,1e-12))[selected])[-12:]]:
    detail=[]
    for i in edges[k]:
        v=mesh.data.vertices[int(i)]
        detail.append(dict(vertex=int(i),source=source[i].tolist(),fitted=fitted[i].tolist(),weights=[(labels[g.group],g.weight)for g in v.groups if g.weight>.001]))
    worst.append(dict(ratio=float(z[k]/a[k]),before_mm=float(a[k]*1000),after_mm=float(z[k]*1000),vertices=detail))
result=dict(profile=tag,samples=rows,worst=worst)
dest=HERE/'hand_repair_20261024'/tag/'arm_deformation_diagnosis.json';dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print('WORST',json.dumps(worst,ensure_ascii=False),flush=True)
