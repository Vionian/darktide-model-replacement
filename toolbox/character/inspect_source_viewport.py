import bpy, json, pathlib, sys
name=sys.argv[sys.argv.index('--')+1]
path=pathlib.Path(r'<SOURCE_ROOT>\Rossia')/(name+'.blend')
bpy.ops.wm.open_mainfile(filepath=str(path))
scene=bpy.context.scene
data={'scene':scene.name,'engine':scene.render.engine,'camera':scene.camera.name if scene.camera else None,
      'view_transform':scene.view_settings.view_transform,'look':scene.view_settings.look,
      'exposure':scene.view_settings.exposure,'world':scene.world.name if scene.world else None,
      'lights':[o.name for o in bpy.data.objects if o.type=='LIGHT'],
      'screens':[],'materials':[]}
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   s=area.spaces.active
   data['screens'].append({'screen':screen.name,'shading':s.shading.type,'light':s.shading.light,
       'studio_light':s.shading.studio_light,'color_type':s.shading.color_type,
       'show_overlays':s.overlay.show_overlays,'show_floor':s.overlay.show_floor,
       'perspective':s.region_3d.view_perspective,'distance':s.region_3d.view_distance,
       'location':list(s.region_3d.view_location),'rotation':list(s.region_3d.view_rotation)})
for mat in bpy.data.materials:
 if mat.node_tree and any(x in mat.name.lower() for x in ('face','cloth_01','hair_01')):
  nodes=[]
  for n in mat.node_tree.nodes:
   nodes.append({'name':n.name,'type':n.type,'label':n.label,'group':n.node_tree.name if n.type=='GROUP' and n.node_tree else None,
      'inputs':{i.name:(list(i.default_value) if hasattr(i.default_value,'__len__') else i.default_value)
        for i in n.inputs if hasattr(i,'default_value')},
      'image':n.image.name if n.type=='TEX_IMAGE' and n.image else None})
  data['materials'].append({'name':mat.name,'nodes':nodes,
      'diffuse_color':list(mat.diffuse_color),'roughness':mat.roughness,'metallic':mat.metallic,
      'links':[{'from':l.from_node.name+'.'+l.from_socket.name,'to':l.to_node.name+'.'+l.to_socket.name}
               for l in mat.node_tree.links]})
print(json.dumps(data,ensure_ascii=False,default=str))
