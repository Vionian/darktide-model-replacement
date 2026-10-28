"""Exercise an asset upgrade in an isolated copy of the old registration fixture."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
GAME=Path('<DARKTIDE_GAME>')
TEST=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'build/registration_upgrade_test'
assert TEST.is_relative_to(ROOT),'Keep the registration fixture inside the project.'
assert not TEST.exists(),'Preserve previous result; choose another isolated fixture.'
shutil.copytree(ROOT/'build/registration_test',TEST)
shutil.copytree(ROOT/'WeaponModelReplacement',TEST/'mods/WeaponModelReplacement',dirs_exist_ok=True)
exe=TEST/'tools/custom-assets-patcher.exe'
original=hashlib.sha256((GAME/'bundle/bundle_database.data').read_bytes()).hexdigest()
logs=[];fixtures=[]
for attempt in range(40):
    r=subprocess.run([str(exe),'--dry-run'],cwd=TEST,capture_output=True,text=True,errors='replace')
    out=r.stdout+r.stderr;logs.append(out)
    if r.returncode==0:break
    match=re.search(r'bundle/([0-9a-f]{16}(?:[.]patch_[0-9]+)?)',out.replace(chr(92),'/'))
    if not match:raise RuntimeError(out)
    name=match.group(1);source=GAME/'bundle'/name;target=TEST/'bundle'/name
    assert source.is_file() and not target.exists(),out
    shutil.copyfile(source,target);fixtures.append({'name':name,'size':source.stat().st_size})
else:raise RuntimeError('Fixture dependency limit exceeded')
assert '1 ready' in out and '0 skipped' in out,out
for args in ([],['--dry-run']):
    r=subprocess.run([str(exe),*args],cwd=TEST,capture_output=True,text=True,errors='replace')
    out=r.stdout+r.stderr;logs.append(out)
    assert r.returncode==0,out
    print(out,flush=True)
assert '0 bundle(s), 0 stream(s)' in out and 'no database change' in out,out
assert hashlib.sha256((GAME/'bundle/bundle_database.data').read_bytes()).hexdigest()==original
manifest=json.loads((TEST/'tools/custom-assets-manifest.json').read_text())
report={'upgrade_registration_passed':True,'repeat_dry_run_no_changes':True,'skipped':0,
    'installed_game_database_unchanged':True,'fixtures':fixtures,'patch':manifest['patch']}
(ROOT/'build/registration_upgrade_audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
(ROOT/'build/registration_upgrade.log').write_text('\n'.join(logs),encoding='utf-8')
print('UPGRADE_REGISTRATION_OK',json.dumps(report),flush=True)
