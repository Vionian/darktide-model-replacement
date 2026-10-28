import bpy, pathlib, json, sys
name=sys.argv[sys.argv.index('--')+1]
root=pathlib.Path(r'<SOURCE_ROOT>\Rossia')
bpy.ops.wm.open_mainfile(filepath=str(root/(name+'.blend')))
rows={'objects':[],'images':[],'materials':[]}
for o in bpy.data.objects:
 if o.type!='MESH': continue
 pts=[o.matrix_world@v.co for v in o.data.vertices]
 rows['objects'].append({'name':o.name,'vertices':len(pts),'bounds':[[min(p[i] for p in pts),max(p[i] for p in pts)] for i in range(3)],'parent':o.parent.name if o.parent else None,'hide_render':o.hide_render,'materials':[m.name if m else None for m in o.data.materials]})
for m in bpy.data.materials:
 if not m or not m.node_tree: continue
 mats=[]
 for n in m.node_tree.nodes:
  if n.type=='TEX_IMAGE' and n.image:
   mats.append({'name':n.name,'image':n.image.name,'path':bpy.path.abspath(n.image.filepath),'size':list(n.image.size),'color_space':n.image.colorspace_settings.name,'packed':bool(n.image.packed_file)})
 if mats: rows['materials'].append({'name':m.name,'images':mats})
for im in bpy.data.images:
 if im.size[0]: rows['images'].append({'name':im.name,'path':bpy.path.abspath(im.filepath),'size':list(im.size),'color_space':im.colorspace_settings.name,'packed':bool(im.packed_file)})
out=pathlib.Path(r'<CHARACTER_WORKSPACE>\tools\model-work\distribution_fix')/(name+'_source_inspection.json')
out.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print('INSPECTED',name,len(rows['objects']),len(rows['materials']),len(rows['images']))
