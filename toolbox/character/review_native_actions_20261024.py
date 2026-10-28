"""Render serialized arms with existing production-Lua synthetic pose outputs."""
from pathlib import Path
import argparse,json,subprocess,hashlib,datetime
from repair_native_hands_20261024 import ROOT,HERE,OUT,REPAIR,BLENDER,LEGACY,fingerprints
def run(tag,poses):
    base=REPAIR/tag if tag in LEGACY else OUT/tag
    status=json.loads((base/'native_repair_status.json').read_text(encoding='utf8'))
    assert status['ok'] and status['pipeline_sha256']==fingerprints(),('Not current complete build',tag)
    unit=base/'Custom'/(tag+'_arms')/(tag+'_arms.unit')
    unit_sha=hashlib.sha256(unit.read_bytes()).hexdigest()
    started=datetime.datetime.now().isoformat()
    selector=['--model-profile'if tag in LEGACY else '--skin-profile',tag]
    result=[]
    for pose in poses:
        data=base/('arms_'+pose+'_pose.json');assert data.exists(),data
        dest=REPAIR/tag/('action_'+pose);dest.mkdir(parents=True,exist_ok=True)
        args=selector+['--asset-dir',str(base/'Custom'/(tag+'_arms')),'--serialized-geometry','--first-person','--individual-hands',
            '--runtime-pose',str(data),'--output-dir',str(dest),'--views','front','back']
        with(dest/'render.log').open('w',encoding='utf8')as stream:
            p=subprocess.run([BLENDER,'-b','--threads','2','--python-exit-code','1','--python',str(HERE/'preview_native_hands_20261024.py'),'--',*args],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        assert p.returncode==0,(tag,pose,(dest/'render.log').read_text(encoding='utf8',errors='replace')[-1800:])
        images=[str(f)for f in dest.glob('*.png')];assert len(images)==4,(tag,pose,images)
        result.append(dict(pose=pose,images=images,actual_serialized_geometry=True,synthetic=True))
        print('ACTION_REVIEW_DONE',tag,pose,flush=True)
    assert hashlib.sha256(unit.read_bytes()).hexdigest()==unit_sha,('Arms changed during action review',tag)
    (REPAIR/tag/'action_checks.json').write_text(json.dumps(dict(profile=tag,poses=result,started_at=started,
        build_started_at=status['started_at'],unit_sha256=unit_sha,pipeline_sha256=fingerprints(),gameplay_verified=False),indent=2),encoding='utf8')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('tag');parser.add_argument('poses',nargs='+');a=parser.parse_args();run(a.tag,a.poses)
