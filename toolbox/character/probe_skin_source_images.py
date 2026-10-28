import bpy,sys,json
from pathlib import Path
HERE=Path(__file__).parent;sys.path.insert(0,str(HERE))
from skins_sources import OUT
tag=sys.argv[sys.argv.index('--')+1]
bpy.ops.wm.open_mainfile(filepath=str(OUT/tag/(tag+'.blend')))
meta=json.loads((OUT/tag/'conversion.json').read_text(encoding='utf8'))
ref=json.loads((OUT/'references'/meta['base']/'source.json').read_text(encoding='utf8'))
mesh=bpy.data.objects[ref['mesh']]
for m in list(mesh.data.materials)[:4]:
    print('MATERIAL',m.name,flush=True)
    for n in m.node_tree.nodes:
        if n.type=='TEX_IMAGE'and n.image:
            im=n.image;print(n.name,im.name,tuple(im.size),len(im.pixels),'packed',bool(im.packed_file),im.filepath,flush=True)
    proxy=bpy.data.objects.get(mesh.name+'__'+m.name)
    if proxy:
        print('PROXY_IMAGES',[(n.image.name,tuple(n.image.size),bool(n.image.packed_file))for pm in proxy.data.materials if pm and pm.node_tree for n in pm.node_tree.nodes if n.type=='TEX_IMAGE'and n.image],flush=True)
print('DIFFUSE_CANDIDATES',[(im.name,tuple(im.size),bool(im.packed_file))for im in bpy.data.images if im.name.startswith('T_actor_')and '_D'in im.name],flush=True)
