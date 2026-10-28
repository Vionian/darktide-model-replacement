from pathlib import Path
import sys,subprocess,concurrent.futures,json,time
from skins_sources import OUT,SOURCES
HERE=Path(__file__).parent
def prepare(key):
    folder=OUT/key;folder.mkdir(exist_ok=True)
    with (folder/'prepare.log').open('w',encoding='utf8')as f:
        r=subprocess.run([sys.executable,str(HERE/'adapt_skins.py'),key],stdout=f,stderr=subprocess.STDOUT)
    print('PREPARE_RESULT',key,r.returncode,flush=True)
    return key,r.returncode
if __name__=='__main__':
    keys=sys.argv[1:]or list(SOURCES)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2)as ex:
        results=list(ex.map(prepare,keys))
    (OUT/'prepare_results.json').write_text(json.dumps(dict(results),indent=2),encoding='utf8')
