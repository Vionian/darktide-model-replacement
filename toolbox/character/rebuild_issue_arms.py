"""Rebuild FP candidates only, retaining audited body binaries."""
from pathlib import Path
import sys, subprocess, concurrent.futures, json
from validate_issue_repairs import ROOT, HERE, OUT, BLENDER
from skins_sources import OUT as SKINS

def build(tag):
    legacy=tag in ('si_lolita','si_short_skirt')
    folder=OUT/tag if legacy else SKINS/tag
    script='build_one_endfield_candidate.py' if legacy else 'build_new_skin.py'
    args=[tag,'--output',str(folder/'Custom'),'--arms-only'] if legacy else [tag,'--arms-only']
    log=OUT/(tag+'_build.log') if legacy else folder/'build.log'
    print('ARMS_START',tag,flush=True)
    with log.open('w',encoding='utf8') as stream:
        result=subprocess.run([BLENDER,'-b','--threads','4','--python-exit-code','1','--python',str(HERE/script),'--',*args],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
    value=log.read_text(encoding='utf8',errors='replace')
    assert result.returncode==0 and 'ROSHIA_BUILD' in value and 'Traceback' not in value,(tag,log)
    print('ARMS_DONE',tag,flush=True)
    return dict(tag=tag,ok=True,body_preserved=True)

if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        rows=list(pool.map(build,sys.argv[1:]))
    print(json.dumps(rows),flush=True)
