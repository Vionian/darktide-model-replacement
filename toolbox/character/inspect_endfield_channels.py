import bpy,pathlib,json
bpy.ops.wm.open_mainfile(filepath=r'<SOURCE_ROOT>\Rossia\提弗洛斯.blend')
m=bpy.data.materials['M_actor_typhoea_cloth_02.001']
lines=[]
def walk(tree,depth=0,seen=None):
    seen=seen or set()
    if tree.name in seen:return
    seen.add(tree.name)
    for n in tree.nodes:
        if n.type=='TEX_IMAGE' and n.image and any(s in n.image.name for s in ('_P.','_N.')):
            lines.append({'tree':tree.name,'image':n.image.name,'destinations':[(l.from_socket.name,l.to_node.name,l.to_socket.name)for l in tree.links if l.from_node==n]})
        if n.type=='GROUP' and n.node_tree:
            inputs=[(i.name,str(i.default_value))for i in n.inputs if any(s in i.name.lower()for s in ('rough','smooth','metal','normal','opacity','alpha')) and hasattr(i,'default_value')]
            if inputs:lines.append({'group':n.name,'tree':n.node_tree.name,'inputs':inputs})
            if depth<3:walk(n.node_tree,depth+1,seen)
walk(m.node_tree)
from character_material_bridge_user import core
for name in ('M_actor_typhoea_cloth_02.001','M_actor_typhoea_cloth_04.001','M_actor_typhoea_cloth_05.001'):
    snap=core.read_material_column(bpy.data.materials[name])
    if snap:
        part,col,width,pix=snap
        vals={}
        for param in core.param_names(part):
            if any(s in param.lower()for s in ('rough','smooth','metal','normal','alpha','opacity','bump')):
                vals[param]=core.read_param(pix,width,col,part,param)
        lines.append({'material':name,'parameters':vals})
path=pathlib.Path(__file__).parent/'endfield_batch/channels_inspection.json'
path.write_text(json.dumps(lines,ensure_ascii=False,indent=2),encoding='utf-8')
print('CHANNELS_DONE')
