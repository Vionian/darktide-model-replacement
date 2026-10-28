"""Read original face layers and CMB parameters without modifying source files."""
import bpy,json,pathlib,sys,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from endfield_profiles import apply
import build_roshia_native as b
from character_material_bridge_user import core
out=pathlib.Path(__file__).parent/'endfield_batch/face_refinement';out.mkdir(exist_ok=True)
keys=sys.argv[sys.argv.index('--')+1:]if '--'in sys.argv else ['zhuangfangyi']
for key in keys:
    apply(b,key);bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
    mesh=bpy.data.objects[b.MESH_OBJECT_NAME];arm=bpy.data.objects[b.ARMATURE_OBJECT_NAME]
    mesh.data.calc_loop_triangles()
    result={'shape_keys':[],'materials':[]}
    if mesh.data.shape_keys:
        basis=mesh.data.shape_keys.key_blocks[0]
        for s in mesh.data.shape_keys.key_blocks:
            n=sum((s.data[i].co-basis.data[i].co).length>.0001 for i in range(len(basis.data)))
            result['shape_keys'].append({'name':s.name,'value':s.value,'changed_vertices':n})
    for index,mat in enumerate(mesh.data.materials):
        if index>7:continue
        proxy=bpy.data.objects.get(mesh.name+'__'+mat.name)
        params={}
        if proxy:
            for pm in proxy.data.materials:
                snap=core.read_material_column(pm)
                if not snap:continue
                part,col,width,data=snap
                params={n:core.read_param(data,width,col,part,n)for n in core.param_names(part)};break
        n=mat.node_tree.nodes.get('mmd_base_tex')if mat.node_tree else None
        if n and n.image:
            n.image.save_render(str(out/(key+'_'+str(index)+'_source.png')))
        normals=np.array([mesh.data.corner_normals[l].vector[:] for t in mesh.data.loop_triangles if t.material_index==index for l in t.loops])
        result['materials'].append({'index':index,'name':mat.name,'params':params,
            'normal_mean':normals.mean(0).tolist()if len(normals)else None})
    (out/(key+'_inspection.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('FACE_INSPECTION',key,flush=True)
