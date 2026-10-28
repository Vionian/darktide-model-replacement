"""Read back final units: native contracts, unchanged topology/UV/weights, surface deltas."""
import pathlib,sys,json,hashlib
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
HERE=pathlib.Path(__file__).parent/'endfield_batch'
BEFORE=HERE/'hand_optimization_before_20261019'
KEYS=('lizhiyan','endministrator_f','si','typhoea')
report={}
def unit(folder,key):return b.unit_dt.UnitResourceDT(b.Cursor(str(folder/(key+'.unit'))))
def channel(g,key,method):
    c=next(c for c in g.channels if c.component.name==key)
    return np.asarray(getattr(g.streams[c.stream],method)(c))
for key in KEYS:
    asset=key+'_arms'
    old=unit(BEFORE/key/'Custom'/asset,asset)
    new=unit(HERE/key/'Custom'/asset,asset)
    assert len(old.mesh_geometries)==len(new.mesh_geometries)
    assert len(old.scene_graph.nodes)==len(new.scene_graph.nodes)
    bind=max(float(abs(np.asarray(a.world_transform)-np.asarray(z.world_transform)).max())
             for a,z in zip(old.scene_graph.nodes,new.scene_graph.nodes))
    assert bind==0,(key,bind)
    inv=max(float(abs(np.asarray(a)-np.asarray(z)).max())for a,z in zip(old.skins[0].inv_bind_matrices,new.skins[0].inv_bind_matrices))
    assert inv==0,(key,inv)
    deltas=[]
    for a,z in zip(old.mesh_geometries,new.mesh_geometries):
        for name,method in (('BLENDINDICES','get_blendindices'),('BLENDWEIGHTS','get_blendweights'),('TEXCOORD','get_texcoords')):
            assert np.array_equal(channel(a,name,method),channel(z,name,method)),(key,name)
        ap=channel(a,'POSITION','get_positions');zp=channel(z,'POSITION','get_positions')
        assert np.isfinite(zp).all()
        deltas.extend(np.linalg.norm(zp-ap,axis=1).tolist())
    deltas=np.asarray(deltas)
    assert deltas.max()>.0001,(key,'Surface optimization had no effect')
    # Whole-body build is deliberately unchanged: first-person fitting is
    # independently authored rather than disturbing the accepted body rig.
    body=HERE/key/'Custom'/key
    oldbody=BEFORE/key/'Custom'/key
    unchanged=all(hashlib.sha256(f.read_bytes()).digest()==hashlib.sha256((oldbody/f.relative_to(body)).read_bytes()).digest()
                  for f in body.rglob('*') if f.is_file() and f.name!='compile_manifest.json')
    assert unchanged,(key,'Unexpected body modification')
    mmr=json.loads((HERE/key/'mmr_hand_authoring.json').read_text(encoding='utf-8'))
    assert mmr['MMR_mappings']==32
    assert len(mmr['source_MMR_motion_probes'])==7
    assert all(r['transverse_center_offset_mm']==[0.,0.]for r in mmr['joints'])
    report[key]={'native_world_bind_change':bind,'inverse_bind_change':inv,
                 'UV_weights_preserved':True,'body_resources_unchanged':unchanged,
                 'changed_vertices':int((deltas>1e-6).sum()),
                 'maximum_surface_change_mm':float(deltas.max()*1000),
                 'MMR_original_source_joints':32,'MMR_synthetic_source_motion_cases':7}
(HERE/'hand_optimization_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ENDFIELD_HAND_OPTIMIZATION_AUDIT',json.dumps(report))
