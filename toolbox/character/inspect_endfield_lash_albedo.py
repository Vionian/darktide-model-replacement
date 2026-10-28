"""Trace the actual CMB lash output and its raw diffuse without source edits."""
import bpy,pathlib,sys,json,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from endfield_profiles import apply
from character_material_bridge_user import core
out=pathlib.Path(__file__).parent/'endfield_batch/face_refinement'
result={}
def trace(socket,depth=0):
    if depth>5:return '...'
    if not socket.is_linked:
        value=getattr(socket,'default_value',None)
        return list(value)if hasattr(value,'__len__')and not isinstance(value,str)else value
    link=socket.links[0];n=link.from_node
    row={'node':n.name,'type':n.type,'output':link.from_socket.name}
    if n.type=='TEX_IMAGE':row['image']=n.image.filepath if n.image else None
    if n.type=='GROUP':
        row['group']=n.node_tree.name
        output=next(z for z in n.node_tree.nodes if z.type=='GROUP_OUTPUT')
        row['internal']=trace(output.inputs[link.from_socket.name],depth+1)
    else:row['inputs']={s.name:trace(s,depth+1)for s in n.inputs if hasattr(s,'default_value')}
    return row
for key in ('liino','gilberta'):
    apply(b,key);bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
    mesh=bpy.data.objects[b.MESH_OBJECT_NAME];arm=bpy.data.objects[b.ARMATURE_OBJECT_NAME];b.prepare_source(mesh,arm)
    m=next(m for m in mesh.data.materials if m.name=='睫眉')
    im=m.node_tree.nodes.get('mmd_base_tex').image
    px=np.asarray(im.pixels[:]).reshape(im.size[1],im.size[0],4)
    row={'image':im.filepath,'raw_mean':px[:,:,:3].mean((0,1)).tolist()}
    obj=bpy.data.objects[mesh.name+'__'+m.name];mat=obj.data.materials[0]
    snap=core.read_material_column(mat);part,col,width,data=snap
    row['params']={n:core.read_param(data,width,col,part,n)for n in core.param_names(part)}
    tree=mat.node_tree;group=next(n for n in tree.nodes if n.type=='GROUP'and 'Z0_r_albedo'in n.outputs)
    row['group_inputs']={s.name:trace(s)for s in group.inputs if s.is_linked}
    row['albedo']=trace(next(n for n in group.node_tree.nodes if n.type=='GROUP_OUTPUT').inputs['Z0_r_albedo'])
    result[key]=row
(out/'lash_albedo_trace.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print('LASH_ALBEDO_TRACE_DONE')
