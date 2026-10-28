import bpy,json,pathlib,collections,numpy as np
bpy.ops.wm.open_mainfile(filepath=r'<SOURCE_ROOT>\Rossia\祀.blend')
m=bpy.data.objects['祀_mesh'];a=bpy.data.objects['祀_arm'];gn={g.index:g.name for g in m.vertex_groups}
data={}
for v in m.data.vertices:
    for g in v.groups:
        if g.weight>.5 and 'sleeve' in gn[g.group].lower():data.setdefault(gn[g.group],[]).append(list(m.matrix_world@v.co))
r=[]
for n,ps in data.items():
    p=np.array(ps);r.append({'name':n,'vertices':len(ps),'min':p.min(0).tolist(),'max':p.max(0).tolist(),'parent':a.data.bones[n].parent.name})
out=pathlib.Path(__file__).parent/'endfield_batch/si_sleeves.json';out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print('SLEEVE_DONE')
