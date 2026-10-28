"""Render matched actual unit surfaces; synthetic poses are explicitly labeled."""
from pathlib import Path
import concurrent.futures,json,subprocess,sys,time
from repair_native_hands_20261024 import ROOT,HERE,OUT,REPAIR,BLENDER,LEGACY,fingerprints
FOCUS={'roshia_lolita','roshia_cocoa_puff','endministrator_penguin','endministrator_devil',
       'si_ink_wash','si_lolita','si_short_skirt','chenqianyu_sport'}
def render(tag):
    legacy=tag in LEGACY;folder=REPAIR/tag if legacy else OUT/tag
    report=folder/'native_repair_checks.json';deadline=time.monotonic()+3600
    while time.monotonic()<deadline:
        if report.exists():
            data=json.loads(report.read_text(encoding='utf8'))
            if data.get('offline_checks_passed') and data.get('pipeline_sha256')==fingerprints():break
        time.sleep(3)
    else:raise TimeoutError(('Candidate validation did not finish',tag))
    selector=['--model-profile',tag] if legacy else ['--skin-profile',tag]
    results=[]
    for pose in (('rest','reload') if tag in FOCUS else ('rest',)):
        dest=REPAIR/tag/('preview_'+pose);dest.mkdir(parents=True,exist_ok=True)
        args=selector+['--asset-dir',str(folder/'Custom'/(tag+'_arms')),'--first-person','--individual-hands',
            '--runtime-pose',str(folder/('arms_'+pose+'_pose.json')),'--output-dir',str(dest),'--views','front']
        log=dest/'render.log'
        print('RENDER_START',tag,pose,flush=True)
        with log.open('w',encoding='utf8') as stream:
            r=subprocess.run([BLENDER,'-b','--threads','2','--python-exit-code','1','--python',str(HERE/'preview_native_hands_20261024.py'),'--',*args],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        text=log.read_text(encoding='utf8',errors='replace');images=list(dest.glob('*.png'))
        if r.returncode or 'Traceback' in text or len(images)!=2:raise ValueError((tag,pose,str(log),text[-1800:]))
        results.append(dict(pose=pose,synthetic=True,images=[str(p) for p in images]))
        print('RENDER_DONE',tag,pose,flush=True)
    result=dict(profile=tag,poses=results,serialized_geometry_compared=True,gameplay_verified=False)
    (REPAIR/tag/'preview_checks.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result
if __name__=='__main__':
    rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        for tag in sys.argv[1:]:
            try:rows.append(render(tag))
            except Exception as ex:
                print('RENDER_FAILED',tag,str(ex),flush=True);rows.append(dict(profile=tag,error=str(ex)))
    (REPAIR/'preview_results.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
    if any('error' in r for r in rows):sys.exit(1)
