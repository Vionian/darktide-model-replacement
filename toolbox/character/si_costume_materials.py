"""Native opaque PBR adaptation of the two locally supplied EFMI costumes.

Diffuse/normal/light-map identities are explicit INI bindings. The packages
do not include RabbitFx shader source; the roughness/metal caps are declared
Darktide art choices, not a claim to reproduce that shader.
"""
from pathlib import Path
import json
import numpy as np

def surface_maps(b,mat,index):
    from endfield_surface_materials import pixels
    def read(key):
        path=mat.get('costume_'+key)
        if not path:return None
        im=b.bpy.data.images.load(path,check_existing=True)
        return pixels(im)
    result={};skin=bool(mat.get('costume_skin'))
    data=read('normal')
    if data is not None:
        xy=np.stack((data[:,:,0]*data[:,:,3],data[:,:,1]),axis=-1)*2-1
        xy*=.15 if skin else .45;xy[:,:,1]*=-1
        xy/=np.maximum(np.linalg.norm(xy,axis=2,keepdims=True),1)
        nm=np.ones_like(data);nm[:,:,:2]=xy*.5+.5
        nm[:,:,2]=np.sqrt(np.maximum(0,1-(xy*xy).sum(2)));result['nm']=nm
    packed=read('packed')
    if packed is not None:
        orm=np.ones_like(packed)
        orm[:,:,1]=np.clip(1-packed[:,:,3],.58,.94)
        orm[:,:,2]=np.clip(packed[:,:,0],0,.65)
    else:orm=np.array([[[1.,.64 if skin else .88,0.,1.]]],np.float32)
    result['orm']=orm
    output=getattr(b,'HAND_AUTHORING_OUTPUT',None)
    if output:
        path=Path(output)/'costume_surfaces.json'
        report=json.loads(path.read_text(encoding='utf8'))if path.exists()else {}
        report[str(index)]=dict(name=mat.name,skin=skin,
            diffuse=mat.get('costume_diffuse'),normal=mat.get('costume_normal'),light_map=mat.get('costume_packed'),
            roughness_quantiles=np.quantile(orm[:,:,1],[0,.5,1]).tolist(),
            metallic_quantiles=np.quantile(orm[:,:,2],[0,.5,1]).tolist(),
            provider='substance_basic',policy='Explicit native PBR art adaptation; RabbitFx source unavailable')
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    return result

def install(b):
    original_surface=b.material_surface_maps
    b.material_surface_maps=lambda mesh,i:surface_maps(b,mesh.data.materials[i],i)if 'costume_profile'in mesh.data.materials[i]else original_surface(mesh,i)
    original_alpha=b.material_is_alpha
    b.material_is_alpha=lambda i,name:False if name.startswith('Costume_')else original_alpha(i,name)
    def chunks(counts):
        import math
        mesh=b.bpy.data.objects[b.MESH_OBJECT_NAME]
        allocation={i:math.ceil(c/(10922 if b.material_is_alpha(i,mesh.data.materials[i].name)else 21845))
                    for i,c in enumerate(counts)if c}
        if sum(allocation.values())>b.GEO_COUNT:raise ValueError(('Costume geometry-slot overflow',allocation))
        while sum(allocation.values())<b.GEO_COUNT:
            i=max(allocation,key=lambda j:counts[j]/allocation[j]);allocation[i]+=1
        return allocation
    b.allocate_chunks=chunks
    original_collect=b.collect_triangles
    def collect(*args,**kwargs):
        groups=original_collect(*args,**kwargs)
        from costume_cuff_fit import apply as fit_cuffs
        fit_cuffs(b,args[0],groups,args[5],args[6],args[7])
        from costume_geometry_audit import rigid_accessories, record
        accessories=rigid_accessories(b,args[0],groups,args[6])
        record(b,args[0],groups,args[5],args[7],accessories)
        if args[7] and getattr(b,'COSTUME_FP_CLEARANCE',False):
            from costume_fp_clearance import apply as fp_clearance
            fp_clearance(b,args[0],args[1],groups,args[5])
        from endfield_hand_detail import final_normals
        skin=[dict(g,material_name='肌')for i,g in enumerate(groups)if args[0].data.materials[i].get('costume_skin')]
        if getattr(b,'COSTUME_PROFILE','')=='roshia_lolita' and getattr(b,'COSTUME_HAND_SMOOTHING',False):
            from endfield_hand_detail import smooth_fitted_hands
            smooth_fitted_hands(skin,args[5])
        final_normals(args[0],skin,args[5])
        for i,g in enumerate(groups):
            if not args[0].data.materials[i].get('costume_two_sided'):continue
            tri=g['triangles'];count=len(g['vertices'])
            for field in ('vertices','uv','normals'):
                reverse=g[field][tri][:,[0,2,1]].copy()
                if field=='normals':reverse*=-1
                g[field]=np.concatenate((g[field],reverse),axis=0)
            g['triangles']=np.concatenate((tri,np.arange(count,count+len(tri),dtype=np.int64)))
        return groups
    b.collect_triangles=collect
