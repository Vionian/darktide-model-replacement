"""Bake actual CMB albedo outputs, excluding its environment/toon final light."""
import bpy,pathlib,sys,json,numpy as np,hashlib,argparse
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from endfield_profiles import apply
parser=argparse.ArgumentParser()
parser.add_argument('keys',nargs='*',default=['zhuangfangyi'])
parser.add_argument('--include-material',action='append',default=[],help='Additional source-specific unlit albedo layers')
parser.add_argument('--eye-style',action='store_true',help='Transfer authored CMB eye ramp/matcap color; explicitly not an unlit albedo')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]if '--'in sys.argv else [])
keys=args.keys
for key in keys:
 apply(b,key);b.INCLUDE_FACE_OUTLINE=False
 bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
 # Resolve moved source textures in memory only. Never save over the blend.
 for image in bpy.data.images:
    if image.source!='FILE' or image.packed_file:continue
    path=pathlib.Path(bpy.path.abspath(image.filepath))
    if path.exists():continue
    alternatives=list(path.parent.parent.rglob(path.name)) if path.parent.parent.exists() else []
    if len(alternatives)==1:image.filepath=str(alternatives[0]);image.reload()
 mesh=bpy.data.objects[b.MESH_OBJECT_NAME]
 arm=bpy.data.objects[b.ARMATURE_OBJECT_NAME];b.prepare_source(mesh,arm)
 out=pathlib.Path(__file__).parent/'endfield_batch/face_refinement'/key;out.mkdir(exist_ok=True)
 scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=1
 scene.render.bake.margin=8;scene.render.bake.use_clear=True
 for obj in scene.objects:obj.hide_render=True
 report=[]
 for i,m in enumerate(mesh.data.materials):
    if m.name not in ('面','目','目1','目2','目白','睫','眉','睫眉','二重','目HL','目1HL','目2HL','口','口内') and m.name not in args.include_material:continue
    if args.eye_style and m.name=='面':continue
    obj=bpy.data.objects.get(mesh.name+'__'+m.name)
    if obj is None:raise ValueError('Missing CMB layer '+key+' '+m.name)
    if not obj.users_collection:bpy.context.scene.collection.objects.link(obj)
    obj.hide_render=False
    bpy.ops.object.select_all(action='DESELECT');obj.hide_set(False);obj.hide_render=False
    obj.select_set(True);bpy.context.view_layer.objects.active=obj
    modifiers=[(mod,mod.show_render,mod.show_viewport)for mod in obj.modifiers if mod.type=='NODES']
    for mod,_,_ in modifiers:mod.show_render=False;mod.show_viewport=False
    bpy.context.view_layer.update()
    source_uv=np.asarray([mesh.data.uv_layers.active.data[l].uv[:]for p in mesh.data.polygons if p.material_index==i for l in p.loop_indices])
    authored_uv_name=obj.data.uv_layers.active.name
    proxy_uv=np.asarray([l.uv[:]for l in obj.data.uv_layers.active.data])
    if source_uv.shape!=proxy_uv.shape:
        raise ValueError('CMB layer UV mismatch '+key+' '+m.name)
    uv_delta=float(np.max(np.abs(source_uv-proxy_uv)))
    # Preset revisions can retain older UVs for the same ordered source loops.
    # Bake the actual shader onto current UVs, while its texture lookup keeps
    # the authored proxy UV layer. Never silently replace a source UV stream.
    bake_uv=obj.data.uv_layers.new(name='NativeFaceBakeUV')
    for l,uv in zip(bake_uv.data,source_uv):l.uv=uv
    obj.data.uv_layers.active=bake_uv
    original=obj.data.materials[0];mat=original.copy();obj.data.materials[0]=mat
    nodes=mat.node_tree.nodes
    lookup=nodes.new('ShaderNodeUVMap');lookup.uv_map=authored_uv_name
    # Destination UV selection must not silently change implicit source UVs.
    for node in list(nodes):
        if node.type=='UVMAP'and not node.uv_map:node.uv_map=authored_uv_name
        if node.type=='TEX_COORD':
            for link in list(node.outputs['UV'].links):
                mat.node_tree.links.new(lookup.outputs['UV'],link.to_socket)
        if node.type=='TEX_IMAGE'and not node.inputs['Vector'].is_linked:
            mat.node_tree.links.new(lookup.outputs['UV'],node.inputs['Vector'])
    output_names=('ret_gBuffer0',) if args.eye_style else ('Z0_r_albedo','Z1_r_albedo')
    albedo=next((n.outputs[name]for name in output_names for n in nodes if n.type=='GROUP'and name in n.outputs),None)
    if albedo is None:raise ValueError('No source albedo output for '+m.name)
    output=next(n for n in nodes if n.type=='OUTPUT_MATERIAL');emit=nodes.new('ShaderNodeEmission')
    mat.node_tree.links.new(albedo,emit.inputs['Color']);mat.node_tree.links.new(emit.outputs[0],output.inputs['Surface'])
    im=bpy.data.images.new(key+'_'+m.name+'_albedo',width=1024,height=1024,alpha=True,float_buffer=True)
    im.colorspace_settings.name='Non-Color'
    target=nodes.new('ShaderNodeTexImage');target.image=im;nodes.active=target
    bpy.ops.object.bake(type='EMIT',uv_layer=bake_uv.name)
    arr=np.empty(1024*1024*4,np.float32);im.pixels.foreach_get(arr);arr=arr.reshape(1024,1024,4)
    linear=arr[:,:,:3].copy();arr[:,:,:3]=np.clip(np.where(linear<=.0031308,linear*12.92,1.055*np.maximum(linear,0)**(1/2.4)-.055),0,1)
    arr[:,:,3]=1
    filename=f'{i}_'+('eye_style'if args.eye_style else 'albedo')+'.png'
    b.write_png(out/filename,arr)
    report.append({'index':i,'material':m.name,'node':albedo.node.name,'output':albedo.name,
                   'file':filename,'sha256':hashlib.sha256((out/filename).read_bytes()).hexdigest(),
                   'uv_max_error':0.,'proxy_lookup_uv_difference':uv_delta,
                   'outline_excluded':True,'bake_uv':bake_uv.name,
                   'lookup_uv':authored_uv_name,'explicit_lookup_uv':True,
                   'lighting_baked':bool(args.eye_style),
                   'bake_kind':'CMB fixed authoring eye ramp/matcap color'if args.eye_style else 'unlit CMB albedo',
                   'mean':linear.mean((0,1)).tolist()})
    obj.data.materials[0]=original
    for mod,render,viewport in modifiers:mod.show_render=render;mod.show_viewport=viewport
    obj.hide_render=True
    print('BAKED_CMB_ALBEDO',key,m.name,flush=True)
 (out/('eye_style_report.json'if args.eye_style else 'albedo_report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
