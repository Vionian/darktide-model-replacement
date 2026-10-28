"""Preview actual serialized body resources; no gameplay claims."""
from pathlib import Path
import json,subprocess,sys,hashlib,datetime
from repair_native_hands_20261024 import ROOT,HERE,OUT,REPAIR,BLENDER,LEGACY,fingerprints
def run(tag,focus,views,pose=None):
    base=REPAIR/tag if tag in LEGACY else OUT/tag
    folder=ROOT/'Custom'/tag if tag=='roshia' else base/'Custom'/tag
    if tag!='roshia':
        status=json.loads((base/'native_repair_status.json').read_text(encoding='utf8'))
        assert status['ok'] and status['pipeline_sha256']==fingerprints(),('Current build is not complete',tag)
    asset=folder/(tag+'.unit');asset_sha=hashlib.sha256(asset.read_bytes()).hexdigest()
    started=datetime.datetime.now().isoformat()
    selector=[] if tag=='roshia' else ['--model-profile'if tag in LEGACY else '--skin-profile',tag]
    dest=REPAIR/tag/('body_'+focus);dest.mkdir(parents=True,exist_ok=True)
    args=selector+['--asset-dir',str(folder),'--serialized-geometry','--output-dir',str(dest),'--views',*views]
    if focus!='body':args+=['--focus-region',focus]
    if pose:args+=['--runtime-pose',str(base/('body_'+pose+'_pose.json'))]
    log=dest/'render.log'
    with log.open('w',encoding='utf8')as stream:
        p=subprocess.run([BLENDER,'-b','--threads','2','--python-exit-code','1','--python',str(HERE/'preview_native_hands_20261024.py'),'--',*args],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
    if p.returncode:raise RuntimeError((tag,focus,str(log),log.read_text(encoding='utf8',errors='replace')[-1700:]))
    assert hashlib.sha256(asset.read_bytes()).hexdigest()==asset_sha,('Body resource changed during review',tag)
    result=dict(profile=tag,focus=focus,pose=pose,started_at=started,unit_sha256=asset_sha,actual_serialized_geometry=True,images=[str(f)for f in dest.glob('*.png')],gameplay_verified=False)
    (dest/'checks.json').write_text(json.dumps(result,indent=2),encoding='utf8');print('BODY_REVIEW_DONE',tag,focus,flush=True)
    return result
if __name__=='__main__':
    tag=sys.argv[1]
    if tag=='roshia':
        run(tag,'face',['front','three-quarter']);run(tag,'tail',['back','side'])
    else:run(tag,'upper-body',['front','back'],'rest')
