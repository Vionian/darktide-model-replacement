import bpy,pathlib,sys,json,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from endfield_wave2 import PROFILES
from endfield_surface_materials import authored_settings
out=pathlib.Path(__file__).parent/'endfield_batch';report={}
for key,p in PROFILES.items():
    bpy.ops.wm.open_mainfile(filepath=str(pathlib.Path(r'<SOURCE_ROOT>\Rossia')/(p['name']+'.blend')))
    mesh=bpy.data.objects[p['name']+'_mesh'];mesh.data.calc_loop_triangles()
    rows=[];cache={}
    for i,m in enumerate(mesh.data.materials):
        n=m.node_tree.nodes.get('mmd_base_tex')if m.node_tree else None
        image=n.image if n and n.type=='TEX_IMAGE'else None
        proxy=bpy.data.objects.get(mesh.name+'__'+m.name)
        settings=authored_settings(proxy)if proxy else {}
        row={'index':i,'name':m.name,'diffuse_color':list(m.diffuse_color),'image':image.name if image else None,
            'settings':settings,'proxy':proxy.name if proxy else None,
            'proxy_images':sorted({n.image.name for pm in proxy.data.materials if pm and pm.node_tree for n in pm.node_tree.nodes if n.type=='TEX_IMAGE'and n.image})if proxy else []}
        if image and image.size[0] and ('Alpha'in m.name or '尾'in m.name):
            if image.name not in cache:
                w,h=image.size;pixels=np.empty(w*h*4,np.float32);image.pixels.foreach_get(pixels);cache[image.name]=pixels.reshape(h,w,4)
            data=cache[image.name];h,w=data.shape[:2]
            uv=mesh.data.uv_layers.active.data
            samples=[]
            for t in mesh.data.loop_triangles:
                if t.material_index!=i:continue
                coords=np.asarray([uv[l].uv for l in t.loops]);coords=np.vstack((coords,coords.mean(0)))
                samples.extend(data[(coords[:,1]*h).astype(int)%h,(coords[:,0]*w).astype(int)%w,3])
            row['used_UV_alpha']={'fraction_below_half':float((np.asarray(samples)<.5).mean()),'mean':float(np.mean(samples))}
        rows.append(row)
    report[key]=rows
    (out/'wave2_material_inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('WAVE2_MATERIAL_INSPECTION_DONE',flush=True)
