"""Read actual compiled replacement joint contracts (Blender Python)."""
import json, pathlib, sys
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
out=pathlib.Path(sys.argv[sys.argv.index('--')+1])
report={}
reference_worlds={}
for asset in ('daniya_blue_arms','daniya_red_arms','qianxia_arms','aimisi_arms','roshia_arms'):
    folder=b.ROOT/'Custom'/asset
    unit=b.unit_dt.UnitResourceDT(b.Cursor(str(folder/(asset+'.unit'))))
    bones=next(folder.glob('*.bones'))
    names=b.named_node_map(unit,b.BonesResourceDT(b.Cursor(str(bones))))
    reference_worlds[asset]={n:np.array(unit.scene_graph.nodes[i].world_transform)
        for n,i in names.items() if n.startswith(('j_lefthand','j_righthand','j_leftinhand','j_rightinhand'))}
    def node(name):
        return names.get(name,names.get('r'+name[1:]))
    def point(name):return np.array(unit.scene_graph.nodes[node(name)].world_transform.translation)
    record={}
    for side in ('left','right'):
        prefix=f'j_{side}hand'
        wrist=point(prefix)
        record[side]={'wrist':wrist.tolist(),'palm_width_mm':float(np.linalg.norm(point(prefix+'index1')-point(prefix+'pinky1'))*1000),'digits':{}}
        for digit in ('thumb','index','middle','ring','pinky'):
            pts=np.array([point(prefix+digit+str(k)) for k in (1,2,3)])
            record[side]['digits'][digit]={'root_from_wrist_mm':((pts[0]-wrist)*1000).tolist(),
                'segments_mm':(np.linalg.norm(np.diff(pts,axis=0),axis=1)*1000).tolist(),
                'points':pts.tolist()}
    report[asset]=record
out.parent.mkdir(parents=True,exist_ok=True)
for name,r in report.items():
    print(name, 'palm_mm',round(r['right']['palm_width_mm'],2),
          'index_segments',r['right']['digits']['index']['segments_mm'],
          'thumb_root_mm',r['right']['digits']['thumb']['root_from_wrist_mm'])
baseline=reference_worlds['qianxia_arms']
report['_reference_matrix_comparison']={name:{
    'nodes_compared':len(baseline),
    'max_matrix_error':max(float(abs(worlds[n]-m).max()) for n,m in baseline.items())}
    for name,worlds in reference_worlds.items() if name!='roshia_arms'}
out.write_text(json.dumps(report,indent=2))
