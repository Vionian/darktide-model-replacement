import pathlib,sys,json
import bpy,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
m=bpy.data.objects[b.MESH_OBJECT_NAME];a=bpy.data.objects[b.ARMATURE_OBJECT_NAME]
m.data.calc_loop_triangles()
groups={g.index:g.name for g in m.vertex_groups}
tw=np.array([sum(g.weight for g in v.groups if groups[g.group].startswith('tail_base_')) for v in m.data.vertices])
out={}
for i,mat in enumerate(m.data.materials):
    ts=[t for t in m.data.loop_triangles if t.material_index==i and max(tw[list(t.vertices)])>.1]
    if not ts:continue
    vs=sorted(set(v for t in ts for v in t.vertices));uv=np.array([m.data.uv_layers.active.data[l].uv[:] for t in ts for l in t.loops])
    im=b.image_pixels_for(mat);colors=b.sample_image(im,uv)
    out[i]={'name':mat.name,'faces':len(ts),'alpha':b.material_is_alpha(i,mat.name),'skipped':any(s in mat.name for s in b.SKIP_MATERIAL_NAMES),'alpha_min_mean_max':[float(colors[:,3].min()),float(colors[:,3].mean()),float(colors[:,3].max())], 'bounds':np.array([b.source_coordinate3()@(m.matrix_world@m.data.vertices[v].co) for v in vs]).tolist()}
    out[i]['bounds']=[np.min(out[i]['bounds'],axis=0).tolist(),np.max(out[i]['bounds'],axis=0).tolist()]
print('TAIL_DIAGNOSTIC',json.dumps(out,ensure_ascii=False))
print('MATERIALS',[(i,x.name)for i,x in enumerate(m.data.materials)])
print('TAIL_BONES',[(x.name,x.parent.name if x.parent else None,list(x.head_local),list(x.tail_local)) for x in a.data.bones if x.name.startswith('tail_base_')][:6])
u=b.load_target_unit();ns=b.named_node_map(u,b.BonesResourceDT(b.Cursor(str(b.TEMPLATE/'qianxia_bones.bones'))))
print('SKIN',[(len(s.node_indices),[(len(x),x[:5],x[-5:],x==list(range(len(x))))for x in s.matrix_index_sets])for s in u.skins])
print('LODS',[(key,str(value))for key,value in vars(u).items()if 'lod' in key])
print('MESH_OBJECTS',[(x.node_index,x.geometry_index,x.skin_index,x.unk4,x.unk5,x.unk6)for x in u.meshes])
rig=b.dynamic_rig_mapping(m,a,u,ns)
from roshia_proportion_rig import adapt
r=adapt(b,u,ns,rig,False)
print('TAIL_WORLDS',[(x['source_bone'],list(rig['node_transforms'][ns[x['node']]]['world'].translation),list(r['node_transforms'][ns[x['node']]]['world'].translation))for x in rig['runtime_bones']if x['group']=='tail'])
