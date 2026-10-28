import pathlib,sys,json
import bpy,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
folder=pathlib.Path(__file__).parent/'endfield_batch'
p=folder/'color_probe.png'
b.write_png(p,np.array([[[.5,.5,.5,1]]],np.float32))
im=bpy.data.images.load(str(p.resolve()),check_existing=False)
im.colorspace_settings.name='sRGB';srgb=list(im.pixels[:])
im.colorspace_settings.name='Non-Color';raw=list(im.pixels[:])
print('COLOR_PROBE',srgb,raw,flush=True)
bpy.ops.wm.open_mainfile(filepath=r'<SOURCE_ROOT>\Rossia\女管理员.blend')
from character_material_bridge_user import core
rows=[]
for mat in bpy.data.materials:
    if not mat.node_tree:continue
    snap=core.read_material_column(mat)
    if not snap:continue
    part,col,width,pixels=snap
    wanted=('_UseBumpMap','_BumpScale','_RoughnessIntensity','_MetallicIntensity','_UseMetallicGlossMap','_Smoothness','_Metallic','_BaseColor','_Color')
    vals={n:core.read_param(pixels,width,col,part,n) for n in core.param_names(part)if n in wanted}
    rows.append({'material':mat.name,'parameters':vals})
(folder/'color_path_diagnosis.json').write_text(json.dumps({'srgb_pixels':srgb,'raw_pixels':raw,'materials':rows},ensure_ascii=False,indent=2),encoding='utf-8')
print('COLOR_DIAGNOSIS_DONE',flush=True)
from endfield_profiles import apply
apply(b,'endministrator_f')
mesh=bpy.data.objects[b.MESH_OBJECT_NAME];arm=bpy.data.objects[b.ARMATURE_OBJECT_NAME]
b.prepare_source(mesh,arm)
for i,m in enumerate(mesh.data.materials):
    image=b.image_pixels_for(m)
    print('DIFFUSE_COLOR_PATH',i,m.name,image[3],np.mean(image[2][:,:,:3],axis=(0,1)).tolist(),list(m.diffuse_color),list(m.mmd_material.diffuse_color)if hasattr(m,'mmd_material')else '',flush=True)
graphs=[]
for tree in bpy.data.node_groups:
    hits=[n for n in tree.nodes if n.type=='BSDF_PRINCIPLED']
    if not hits:continue
    def ancestors(socket,depth=0):
        if depth>7:return '...'
        if not socket.is_linked:return list(socket.default_value)if hasattr(socket.default_value,'__len__')else socket.default_value
        n=socket.links[0].from_node
        return {'node':n.name,'type':n.bl_idname,'op':getattr(n,'operation',getattr(n,'blend_type','')),
                'output':socket.links[0].from_socket.name,'inputs':{s.name:ancestors(s,depth+1) for s in n.inputs if hasattr(s,'default_value')}}
    for n in hits:graphs.append({'tree':tree.name,'roughness':ancestors(n.inputs['Roughness']),'metallic':ancestors(n.inputs['Metallic'])})
(folder/'source_pbr_graph.json').write_text(json.dumps(graphs,ensure_ascii=False,indent=2),encoding='utf-8')
