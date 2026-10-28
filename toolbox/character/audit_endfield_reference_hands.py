import pathlib,sys,json,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
out=pathlib.Path(__file__).parent/'endfield_batch'
baseline=None;body_baseline=None;report={}
assets=['qianxia_arms','daniya_blue_arms','daniya_red_arms','aimisi_arms','qianxia','roshia_arms',
        'lizhiyan_arms','endministrator_f_arms','si_arms','typhoea_arms']
for asset in assets:
    folder=b.ROOT/'Custom'/asset
    u=b.unit_dt.UnitResourceDT(b.Cursor(str(folder/(asset+'.unit'))))
    names=b.named_node_map(u,b.BonesResourceDT(b.Cursor(str(next(folder.glob('*.bones'))))))
    hands={('j'+n[1:] if n.startswith(('r_lefthand','r_righthand','r_leftinhand','r_rightinhand')) else n):np.asarray(u.scene_graph.nodes[i].world_transform)
           for n,i in names.items() if n.startswith(('j_lefthand','j_righthand','j_leftinhand','j_rightinhand','r_lefthand','r_righthand','r_leftinhand','r_rightinhand'))}
    assert len(hands)==40,(asset,len(hands))
    if baseline is None:baseline=hands
    err=max(float(abs(w-baseline[n]).max())for n,w in hands.items())
    position_error=max(float(abs(w[:3,3]-baseline[n][:3,3]).max())for n,w in hands.items())
    if asset in assets[:4]:
        assert err==0,(asset,err)
    elif asset=='qianxia':
        body_baseline=hands
    else:
        own_error=max(float(abs(w-body_baseline[n]).max())for n,w in hands.items())
        assert own_error<2e-6,(asset,own_error)
    # Cross-file body/arms template quantization difference is reported, not
    # described as bit-identical. Candidate equality uses its actual template.
    report[asset]={'wrist_digit_inhand_nodes':40,'max_world_bind_error_vs_reference_arms':err,
                   'max_position_error_vs_reference_arms_m':position_error,
                   'max_error_vs_build_template':(max(float(abs(w-body_baseline[n]).max())for n,w in hands.items()) if body_baseline else None)}
(out/'reference_hand_contract.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('REFERENCE_HAND_CONTRACT_OK',report)
