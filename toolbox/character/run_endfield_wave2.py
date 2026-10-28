"""Bounded batch runner; each Blender process has a separate output/log folder."""
import pathlib,sys,subprocess,json,concurrent.futures,datetime
from endfield_wave2 import PROFILES
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BLENDER=r'<BLENDER_EXE>'
OUT=HERE/'endfield_batch'
mode=sys.argv[1]if len(sys.argv)>1 else 'build'
keys=sys.argv[2:]or list(PROFILES)
def run(key):
    dest=OUT/key;dest.mkdir(exist_ok=True)
    if mode=='build':jobs=[('build','build_endfield_native.py',[key])]
    elif mode=='assets':jobs=[('asset_audit','audit_endfield_native.py',['assets',key])]
    elif mode=='audit':jobs=[('asset_audit','audit_endfield_native.py',['assets',key]),
        ('contact_audit','audit_endfield_native.py',['lua',key]),
        ('mmr_audit','audit_endfield_native.py',['mmr',key])]
    elif mode in ('final-preview','appearance-preview'):jobs=[
        ('final_body','preview_roshia_native.py',['--model-profile',key,'--asset-dir',str(dest/'Custom'/key),'--output-dir',str(dest/'final_body'),'--views','front']),
        ('final_face','preview_roshia_native.py',['--model-profile',key,'--asset-dir',str(dest/'Custom'/key),'--focus-region','face','--output-dir',str(dest/'final_face'),'--views','front','three-quarter']),
        ('final_hands','preview_roshia_native.py',['--model-profile',key,'--first-person','--individual-hands','--asset-dir',str(dest/'Custom'/(key+'_arms')),'--runtime-pose',str(dest/'arms_staff_pose.json'),'--output-dir',str(dest/'final_hands'),'--views','front'])]
    elif mode=='preview':jobs=[
        ('body_preview','preview_roshia_native.py',['--model-profile',key,'--asset-dir',str(dest/'Custom'/key),'--output-dir',str(dest/'preview_body'),'--views','front','back','side']),
        ('hands_preview','preview_roshia_native.py',['--model-profile',key,'--first-person','--individual-hands','--asset-dir',str(dest/'Custom'/(key+'_arms')),'--output-dir',str(dest/'preview_hands'),'--views','front']),
        ('staff_preview','preview_roshia_native.py',['--model-profile',key,'--first-person','--individual-hands','--asset-dir',str(dest/'Custom'/(key+'_arms')),'--runtime-pose',str(dest/'arms_staff_pose.json'),'--output-dir',str(dest/'preview_staff'),'--views','front'])]
    else:raise ValueError(mode)
    if mode=='appearance-preview':jobs=[j for j in jobs if j[0]!='final_hands']
    for label,script,args in jobs:
        cmd=([sys.executable,'-X','utf8',str(HERE/script),'--']if label=='contact_audit'else[BLENDER,'-b','--threads','6','--python-exit-code','1','--python',str(HERE/script),'--'])+args
        log=dest/(label+'.log')
        print('START',key,label,datetime.datetime.now().isoformat(),flush=True)
        with log.open('w',encoding='utf-8')as stream:r=subprocess.run(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        if r.returncode:
            print('FAILED',key,label,'see',log,flush=True)
            return {'key':key,'ok':False,'stage':label,'log':str(log)}
        print('DONE',key,label,datetime.datetime.now().isoformat(),flush=True)
    return {'key':key,'ok':True,'mode':mode}
with concurrent.futures.ThreadPoolExecutor(max_workers=1 if mode=='preview'else 2)as pool:
    result=list(pool.map(run,keys))
(OUT/('wave2_'+mode+'_status.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
if not all(r['ok']for r in result):sys.exit(1)
