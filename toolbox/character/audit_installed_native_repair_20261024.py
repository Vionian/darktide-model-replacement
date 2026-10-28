"""Verify installed resource hashes; this does not accept gameplay visuals."""
import json,datetime,subprocess
from pathlib import Path
from deploy_native_hand_repair_20261024 import collect,TAGS,ROOT,MOD,REPAIR,sha
files,profiles=collect(TAGS)
for relative,src in files.items():
 assert sha(src)==sha(ROOT/relative)==sha(MOD/relative),relative
runtime=[]
for p in (ROOT/'scripts').rglob('*'):
 if p.is_file():
  relative=p.relative_to(ROOT);assert sha(p)==sha(MOD/relative),relative
  runtime.append(str(relative))
for name in ('AnimeModelReplacement.mod','info.json'):
 if (ROOT/name).exists():assert sha(ROOT/name)==sha(MOD/name),name
latest=json.loads((REPAIR/'deployment_latest.json').read_text(encoding='utf8'))
dry=Path(latest['registration_dry_run_log']).read_text(encoding='utf8')
assert '77 ready, 0 skipped'in dry,dry[-2000:]
assert '0 bundle(s), 0 stream(s) and no database change would be written'in dry,dry[-2000:]
r=subprocess.run(['python','-X','utf8','tools/model-work/test_new_skins.py'],cwd=ROOT,capture_output=True,text=True,encoding='utf8')
assert r.returncode==0,r.stdout+r.stderr
report=dict(checked_at=datetime.datetime.now().isoformat(),profiles=profiles,
 candidate_files=len(files),runtime_files=len(runtime),workspace_installed_source_hashes_match=True,
 registration_dry_run=str(latest['registration_dry_run_log']),registration_pending_changes=False,
 static_settings_test=r.stdout.strip(),gameplay_verified=False,
 limitation='Resource installation, source/compiled matching and synthetic offline poses only; no game camera or native animation acceptance')
(REPAIR/'final_installed_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('INSTALLED_NATIVE_AUDIT_OK',len(TAGS),len(files),len(runtime),r.stdout.strip(),flush=True)
