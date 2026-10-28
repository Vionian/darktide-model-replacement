import bpy
import json
import pathlib
bpy.ops.wm.open_mainfile(filepath='<SOURCE_ROOT>/Rossia/赛希.blend')
mesh=bpy.data.objects['赛希_mesh__丝袜(Cloth1)']
report=[]
for mat in mesh.data.materials:
    report.append({'material':mat.name,'nodes':[{
        'name':n.name,'type':n.type,'tree':n.node_tree.name if n.type=='GROUP' else None,
        'outputs':[s.name for s in n.outputs],
        'links':[(l.from_node.name,l.from_socket.name,l.to_socket.name) for s in n.inputs for l in s.links]
        }for n in mat.node_tree.nodes]})
path=pathlib.Path(__file__).parent/'endfield_batch/wave3_stocking_shader.json'
path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('STOCKING_SHADER',json.dumps(report,ensure_ascii=False))
