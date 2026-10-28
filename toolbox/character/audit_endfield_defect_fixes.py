"""Read back actual candidates, including skin stress and opaque part bindings."""
import pathlib,sys,json,struct
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
OUT=pathlib.Path(__file__).parent/'endfield_batch'
KEYS=('lizhiyan','endministrator_f','si','typhoea')
def load(folder,asset):return b.unit_dt.UnitResourceDT(b.Cursor(str(folder/(asset+'.unit'))))
def channel(g,key,method):
    c=next(c for c in g.channels if c.component.name==key)
    return np.asarray(getattr(g.streams[c.stream],method)(c))
def stress(u,names,worlds):
    mats=np.asarray(worlds)[u.skins[0].node_indices]@np.asarray(u.skins[0].inv_bind_matrices)
    pal=[p for p,n in enumerate(u.skins[0].node_indices)if n in {i for name,i in names.items()if 'handring'in name}]
    ratios=[]
    for g in u.mesh_geometries:
        p=channel(g,'POSITION','get_positions').astype(float)
        ji=channel(g,'BLENDINDICES','get_blendindices').astype(int);w=channel(g,'BLENDWEIGHTS','get_blendweights').astype(float)
        assert np.isfinite(p).all() and np.isfinite(w).all()
        assert abs(w.sum(1)-1).max()<.001 and w.min()>=0
        selected=np.where(np.isin(ji,pal),w,0).sum(1)>.5
        blend=(mats[ji]*w[:,:,None,None]).sum(1)
        q=np.einsum('nij,nj->ni',blend[:,:3,:3],p)+blend[:,:3,3]
        # Builder emits three distinct vertices per triangle, in native order.
        assert len(p)%3==0
        for a,c in ((0,1),(1,2),(2,0)):
            pp=p.reshape(-1,3,3);qq=q.reshape(-1,3,3);s=selected.reshape(-1,3)
            length=np.linalg.norm(pp[:,a]-pp[:,c],axis=1)
            keep=s[:,a]&s[:,c]&(length>.0005)
            ratios.extend((np.linalg.norm(qq[:,a]-qq[:,c],axis=1)[keep]/length[keep]).tolist())
    return {'ring_edge_stretch_p99':float(np.quantile(ratios,.99)),
            'ring_edge_stretch_max':float(max(ratios)),'measured_ring_edges':len(ratios)}
report={}
for key in KEYS:
    asset=key+'_arms';folder=OUT/key/'Custom'/asset
    new=load(folder,asset);old=load(OUT/'defects_before_20261019'/key/asset,asset)
    names=b.named_node_map(new,b.BonesResourceDT(b.Cursor(str(next(folder.glob('*.bones'))))))
    bind=max(float(abs(np.asarray(a.world_transform)-np.asarray(z.world_transform)).max())for a,z in zip(old.scene_graph.nodes,new.scene_graph.nodes))
    inv=max(float(abs(np.asarray(a)-np.asarray(z)).max())for a,z in zip(old.skins[0].inv_bind_matrices,new.skins[0].inv_bind_matrices))
    assert bind==0 and inv==0,(key,bind,inv)
    pose=json.loads((OUT/key/'arms_psyker_charge_pose.json').read_text(encoding='utf-8'))
    before,after=stress(old,names,pose['worlds']),stress(new,names,pose['worlds'])
    # A reference transfer must not create large additional stretch.
    assert after['ring_edge_stretch_p99']<max(1.6,before['ring_edge_stretch_p99']*1.15),(key,before,after)
    opacity={}
    body=OUT/key/'Custom'/key
    manifest=json.loads((body/'build.json').read_text(encoding='utf-8'))
    for index in {'endministrator_f':(15,),'typhoea':(13,14)}.get(key,()):
        name=f'content/mods/{key}/{key}_material_{index}'
        entry=next(e for e in manifest['artifacts']if e['resource']['name']==name and e['role']=='stream')
        data=(body/entry['path']).read_bytes();offset=struct.unpack_from('<I',data,4)[0]
        provider=struct.unpack_from('<Q',data,offset+4)[0]
        assert provider==b.hash64('content/parent_materials/substance_basic'),(key,index,hex(provider))
        opacity[index]='opaque substance_basic'
    surfaces=json.loads((OUT/key/'surface_materials.json').read_text(encoding='utf-8'))
    assert any(r['normal'] for r in surfaces.values())
    assert all('authored_settings'in r for r in surfaces.values())
    mmr=json.loads((OUT/key/'mmr_hand_authoring.json').read_text(encoding='utf-8'))
    assert mmr['MMR_mappings']==32 and len(mmr['source_MMR_motion_probes'])==7
    report[key]={'native_bind_change':bind,'inverse_bind_change':inv,'opaque_slots':opacity,
                 'synthetic_psyker_before':before,'synthetic_psyker_after':after,
                 'source_MMR_joints':32,'source_MMR_synthetic_cases':7,
                 'gameplay_verified':False}
(OUT/'defect_fixes_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('ENDFIELD_DEFECT_FIXES_AUDIT_OK',json.dumps(report))
