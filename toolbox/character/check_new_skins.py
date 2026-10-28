"""Follow fresh builds with serialized, production-Lua and visual checks."""
from pathlib import Path
import sys,json,subprocess,concurrent.futures,time,datetime
from skins_sources import OUT,SOURCES
from adapt_skins import VARIANTS,profile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
tags=sys.argv[1:]or[profile(k,v)for k in SOURCES for v in range(1,VARIANTS[k]+1)]

def run(tag):
    folder=OUT/tag;deadline=time.monotonic()+2400
    while True:
        log=folder/'build.log'
        fresh=log.exists()and log.stat().st_mtime>=(folder/'conversion.json').stat().st_mtime
        text=log.read_text(encoding='utf8',errors='replace')if fresh else ''
        if 'Traceback'in text:return dict(tag=tag,ok=False,stage='build')
        if 'NEW_SKIN_BUILD_DONE '+tag in text:break
        if time.monotonic()>deadline:return dict(tag=tag,ok=False,stage='wait_for_build_timeout')
        time.sleep(3)
    jobs=[('audit',[sys.executable,'-X','utf8',str(HERE/'run_new_skins.py'),'audit',tag]),
          ('contacts',[sys.executable,'-X','utf8',str(HERE/'test_new_skin_contacts.py'),tag]),
          ('preview',[sys.executable,'-X','utf8',str(HERE/'run_new_skins.py'),'preview',tag]),
          ('hand_topology',[r'<BLENDER_EXE>','-b','--threads','4',
                            '--python-exit-code','1','--python',str(HERE/'inspect_costume_hand_edges.py'),'--',tag])]
    for label,args in jobs:
        print('CHECK_START',tag,label,datetime.datetime.now().isoformat(),flush=True)
        with (folder/(label+'_pipeline.log')).open('w',encoding='utf8')as f:
            result=subprocess.run(args,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
        if result.returncode:return dict(tag=tag,ok=False,stage=label)
        print('CHECK_DONE',tag,label,flush=True)
    return dict(tag=tag,ok=True)

if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2)as ex:
        results=list(ex.map(run,tags))
    (OUT/'final_checks.json').write_text(json.dumps(results,indent=2),encoding='utf8')
    print('CHECK_RESULTS',json.dumps(results),flush=True)
    if not all(r['ok']for r in results):sys.exit(1)
