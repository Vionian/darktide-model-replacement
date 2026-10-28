from pathlib import Path
import sys,json,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_roshia_native as b
root=Path(__file__).resolve().parent/'issue_fixes_20261023'
for tag in ('si_lolita','si_short_skirt'):
    folder=root/tag;asset=folder/'Custom'/(tag+'_arms')
    u=b.unit_dt.UnitResourceDT(b.Cursor(str(asset/(tag+'_arms.unit'))))
    names=b.named_node_map(u,b.BonesResourceDT(b.Cursor(str(asset/(tag+'_arms_bones.bones')))))
    pose=json.loads((folder/'arms_reload_pose.json').read_text())
    worlds=np.array(pose['worlds']);pal=u.skins[0].node_indices
    transforms=worlds[pal]@np.array(u.skins[0].inv_bind_matrices)
    resource=json.loads((asset/'build.json').read_text());mats={b.hash64(r['resource']['name']):r['resource']['name'] for r in resource['artifacts']if r['resource']['type']=='material'}
    slots={s.ID:r.ID for s,r in u.materials}
    print(tag)
    for geo in u.mesh_geometries:
        cs={c.component.name:c for c in geo.channels}
        def read(n,m):c=cs[n];return getattr(geo.streams[c.stream],m)(c)
        p=read('POSITION','get_positions');j=read('BLENDINDICES','get_blendindices');w=read('BLENDWEIGHTS','get_blendweights')
        if len(p)==0:continue
        blended=(transforms[j]*w[:,:,None,None]).sum(1);q=np.einsum('nij,nj->ni',blended[:,:3,:3],p)+blended[:,:3,3]
        dist=np.full(len(p),99.)
        for side in ('left','right'):
            pts=[worlds[names['j_'+side+s],:3,3]for s in ('arm','forearm','hand','handmiddle3')]
            for a,z in zip(pts[:-1],pts[1:]):
                ax=z-a;t=np.clip((q-a)@ax/(ax@ax),0,1);dist=np.minimum(dist,np.linalg.norm(q-a-t[:,None]*ax,axis=1))
        bad=dist>.13
        if bad.any():
            mass=np.zeros(len(pal));np.add.at(mass,j[bad].ravel(),w[bad].ravel())
            inv={i:n for n,i in names.items()};top=sorted([(float(v),inv.get(pal[i],str(pal[i])))for i,v in enumerate(mass)],reverse=True)[:5]
            print(mats[slots[geo.materials[0].ID]].rsplit('/',1)[-1],len(p),int(bad.sum()),'max',round(float(dist.max()),3),'weights',top)
