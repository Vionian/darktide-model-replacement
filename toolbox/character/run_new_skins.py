"""Bounded, resumable source costume builds. Never changes installed assets."""
from pathlib import Path
import sys,subprocess,concurrent.futures,json,datetime
from skins_sources import OUT,SOURCES
from adapt_skins import VARIANTS,profile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BLENDER=r'<BLENDER_EXE>'
mode=sys.argv[1] if len(sys.argv)>1 else 'build'
force='--force'in sys.argv
tags=[a for a in sys.argv[2:]if a!='--force'] or [profile(k,v)for k in SOURCES for v in range(1,VARIANTS[k]+1)]
def run(tag):
    folder=OUT/tag
    if mode=='build':
        jobs=[('blend','adapt_skins.py',[tag,'--blend']),('build','build_new_skin.py',[tag])]
    elif mode=='preview':
        jobs=[('preview_body','preview_roshia_native.py',['--skin-profile',tag,'--asset-dir',str(folder/'Custom'/tag),'--output-dir',str(folder/'preview_body'),'--views','front','back']),
              ('preview_hands','preview_roshia_native.py',['--skin-profile',tag,'--first-person','--individual-hands','--asset-dir',str(folder/'Custom'/(tag+'_arms')),'--output-dir',str(folder/'preview_hands'),'--views','front'])]
    elif mode=='audit':
        jobs=[('audit','audit_new_skin.py',[tag])]
    else:raise ValueError(mode)
    for label,script,args in jobs:
        log=folder/(label+'.log')
        marker='NEW_SKIN_BUILD_DONE '+tag if label=='build' else 'OUTFIT_BLEND '+tag
        if not force and label in ('blend','build')and log.exists()and marker in log.read_text(encoding='utf8',errors='replace')and 'Traceback'not in log.read_text(encoding='utf8',errors='replace'):
            print('REUSE',tag,label,flush=True);continue
        print('START',tag,label,datetime.datetime.now().isoformat(),flush=True)
        with log.open('w',encoding='utf8')as f:
            result=subprocess.run([BLENDER,'-b','--threads','6','--python-exit-code','1','--python',str(HERE/script),'--',*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
        if result.returncode or 'Traceback'in log.read_text(encoding='utf8',errors='replace'):
            print('FAILED',tag,label,flush=True);return dict(tag=tag,ok=False,stage=label)
        print('DONE',tag,label,flush=True)
    return dict(tag=tag,ok=True)
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2 if mode in ('build','audit')else 1)as ex:
        results=list(ex.map(run,tags))
    (OUT/(mode+'_results.json')).write_text(json.dumps(results,indent=2),encoding='utf8')
    if not all(r['ok']for r in results):sys.exit(1)
