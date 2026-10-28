from pathlib import Path
import bpy,numpy as np,json
HERE=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(HERE/'skins_20261023/si_ink_wash/si_ink_wash.blend'))
meta=json.loads((HERE/'skins_20261023/references/si/source.json').read_text(encoding='utf8'))
mesh=bpy.data.objects[meta['mesh']];mesh.data.calc_loop_triangles()
mi=next(i for i,m in enumerate(mesh.data.materials)if m.name=='Costume_si_ink_wash_2')
mat=mesh.data.materials[mi];image=bpy.data.images.load(mat['costume_diffuse'],check_existing=True)
w,h=image.size;pixels=np.empty(w*h*4,np.float32);image.pixels.foreach_get(pixels);alpha=pixels.reshape(h,w,4)[:,:,3]
uv=np.asarray([x.uv for x in mesh.data.uv_layers.active.data]);tris=np.asarray([list(t.loops)for t in mesh.data.loop_triangles if t.material_index==mi])
centers=uv[tris].mean(1);xx=(np.mod(centers[:,0],1)*w).astype(int)%w;yy=(np.mod(centers[:,1],1)*h).astype(int)%h
a=alpha[yy,xx]
report=dict(material=mat.name,diffuse=mat['costume_diffuse'],triangles=len(tris),
 alpha_quantiles=np.quantile(a,[0,.1,.25,.5,.75,.9,1]).tolist(),
 face_centers_alpha_below_028=int(np.sum(a<.28)),face_centers_alpha_zero=int(np.sum(a<.001)),
 source_texture_alpha_is_not_exported_by_current_forced_opaque_policy=True)
(HERE/'hand_repair_20261024/si_ink_wash/diffuse_coverage.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print('AUTHORED_ALPHA_COVERAGE',json.dumps(report),flush=True)
