"""Inspect matching UV coordinates/material colors used by source CMB layers."""
import bpy,sys,pathlib,json,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from endfield_profiles import apply
keys=sys.argv[sys.argv.index('--')+1:]
for key in keys:
 apply(b,key);bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
 mesh=bpy.data.objects[b.MESH_OBJECT_NAME];arm=bpy.data.objects[b.ARMATURE_OBJECT_NAME];b.prepare_source(mesh,arm)
 mesh.data.calc_loop_triangles()
 out={}
 for i,m in enumerate(mesh.data.materials):
  if i>7:continue
  proxy=bpy.data.objects.get(mesh.name+'__'+m.name)
  source_uv=np.asarray([mesh.data.uv_layers.active.data[l].uv[:]for p in mesh.data.polygons if p.material_index==i for l in p.loop_indices])
  row={'source_loops':len(source_uv),'material':m.name}
  triangles=[t for t in mesh.data.loop_triangles if t.material_index==i]
  crosses=np.asarray([np.cross(np.asarray(mesh.data.vertices[t.vertices[1]].co)-np.asarray(mesh.data.vertices[t.vertices[0]].co),np.asarray(mesh.data.vertices[t.vertices[2]].co)-np.asarray(mesh.data.vertices[t.vertices[0]].co))for t in triangles])
  if len(crosses):row['front_area_fraction']=float(np.maximum(-crosses[:,1],0).sum()/np.maximum(np.abs(crosses[:,1]).sum(),1e-9))
  if proxy:
   row['proxy_uv_layers']=[l.name for l in proxy.data.uv_layers]
   row['proxy_active_uv']=proxy.data.uv_layers.active.name
   uv=np.asarray([l.uv[:]for l in proxy.data.uv_layers.active.data])
   row['proxy_loops']=len(uv)
   row['proxy_materials']=[m.name for m in proxy.data.materials]
   row['proxy_material_counts']={str(i):sum(p.material_index==i for p in proxy.data.polygons)for i in range(len(proxy.data.materials))}
   row['modifiers']=[{'name':m.name,'type':m.type,'show_render':m.show_render,
                       'thickness':getattr(m,'thickness',None),'node_group':m.node_group.name if m.type=='NODES'and m.node_group else None}for m in proxy.modifiers]
   evaluated=proxy.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
   row['evaluated_vertices']=len(evaluated.vertices)
   row['original_vertices']=len(proxy.data.vertices)
   if len(evaluated.vertices)==len(proxy.data.vertices):
    row['max_modifier_position_delta']=max((a.co-z.co).length for a,z in zip(evaluated.vertices,proxy.data.vertices))
   row['node_operations']={m.node_group.name:[(n.name,n.bl_idname)for n in m.node_group.nodes]for m in proxy.modifiers if m.type=='NODES'and m.node_group}
   row['uv_bounds']=[uv.min(0).tolist(),uv.max(0).tolist()]
   row['source_uv_bounds']=[source_uv.min(0).tolist(),source_uv.max(0).tolist()]
   row['uv_direct_error']=float(np.abs(uv-source_uv).max())if uv.shape==source_uv.shape else None
   mat=proxy.data.materials[0]
   row['attributes']=[{'name':n.name,'attribute':n.attribute_name}for n in mat.node_tree.nodes if n.type=='ATTRIBUTE']
   row['proxy_mesh_attributes']=[a.name for a in proxy.data.attributes]
   row['mmd_diffuse']=list(m.diffuse_color)
  out[str(i)]=row
 dest=pathlib.Path(__file__).parent/'endfield_batch/face_refinement'/key
 dest.mkdir(exist_ok=True)
 (dest/'uv_inspection.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
 print('FACE_UV_INSPECTED',key,flush=True)
