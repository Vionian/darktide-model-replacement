from pathlib import Path
import hashlib,json,re,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
GAME=Path('<DARKTIDE_GAME>')
TEST=ROOT/'build/registration_test'
exe=TEST/'tools/custom-assets-patcher.exe'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
original=sha(GAME/'bundle/bundle_database.data')
logs=[];fixtures=[]
for attempt in range(24):
    r=subprocess.run([str(exe),'--dry-run'],cwd=TEST,capture_output=True,text=True,errors='replace')
    text=r.stdout+r.stderr;logs.append(text)
    if r.returncode==0:break
    match=re.search(r'bundle/([0-9a-f]{16}(?:[.]patch_[0-9]+)?)',text.replace(chr(92),'/'))
    if not match:raise RuntimeError(text)
    name=match.group(1)
    source=GAME/'bundle'/name;target=TEST/'bundle'/name
    assert source.is_file() and not target.exists(),text
    assert target.resolve().is_relative_to((TEST/'bundle').resolve())
    shutil.copyfile(source,target);fixtures.append({'name':name,'size':source.stat().st_size})
    print('COPIED_TEST_FIXTURE',name,flush=True)
else:raise RuntimeError('Fixture dependency count exceeded limit')
assert '1 ready' in text and '0 skipped' in text,text
print(text,flush=True)
for args in ([],['--dry-run']):
    r=subprocess.run([str(exe),*args],cwd=TEST,capture_output=True,text=True,errors='replace')
    text=r.stdout+r.stderr;logs.append(text)
    assert r.returncode==0,text
    print(text,flush=True)
assert '0 bundle(s), 0 stream(s)' in text and 'no database change' in text,text
assert sha(GAME/'bundle/bundle_database.data')==original
report={'ready_assets':1,'skipped':0,'fixtures':fixtures,'clean_registration_passed':True,
        'repeat_dry_run_no_changes':True,'installed_game_database_unchanged':True,
        'installed_game_database_sha256':original,'scope':'scratch fixture only; game not launched'}
(ROOT/'build/registration_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(ROOT/'build/registration.log').write_text(chr(10).join(logs),encoding='utf-8')
print('REGISTRATION_TEST_OK',json.dumps(report),flush=True)
