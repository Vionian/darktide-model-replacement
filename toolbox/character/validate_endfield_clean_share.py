"""Validate the distribution and exercise clean removal/install outside the real game."""
import datetime,json,pathlib,re,shutil,subprocess,sys,zipfile
from package_endfield_clean_share import ROOT,MODELS,KEEP,PROVIDERS,sha,plain,write
sys.path.insert(0,str(ROOT/'tools/model-work/python-deps'))
from lupa.luajit21 import LuaRuntime
from test_native_equipment_lifecycle import audit

GAME=pathlib.Path('<DARKTIDE_GAME>')

def main():
 statepath=ROOT/'tools/model-work/share_20261024_state.json'
 state=json.loads(statepath.read_text(encoding='utf8'))
 backup=pathlib.Path(state['backup'])
 mod=pathlib.Path(state['folder'])/'AnimeModelReplacement'
 archive=pathlib.Path(state['zip'])
 manifest=json.loads((mod/'_setup/package_manifest.json').read_text(encoding='utf8'))
 assets={a for k in KEEP for a in (k,k+'_arms')}
 assert set(manifest['assets'])==assets and manifest['character_count']==16
 assert {p.name for p in (mod/'Custom').iterdir()}==assets
 assert {p.name for p in (mod/'scripts/mods').iterdir()}==PROVIDERS|{'AnimeModelReplacement','CustomAssets','ModelReplacementRegistry'}
 with zipfile.ZipFile(archive) as z:
  assert len(z.namelist())==len(manifest['files'])+1
  assert {n.split('/')[0] for n in z.namelist()}=={'AnimeModelReplacement'}
  import hashlib
  for e in manifest['files']:
   name='AnimeModelReplacement/'+e['path'];h=hashlib.sha256()
   with z.open(name) as f:
    while b:=f.read(1024*1024):h.update(b)
   assert h.hexdigest()==e['sha256'] and sha(mod/e['path'])==e['sha256'],name
  for n in z.namelist():
   assert pathlib.PurePosixPath(n).name not in ['bundle_database.data','user_settings.config','custom-assets-state.json','custom-assets-manifest.lua','Darktide.exe','oo2core_9_win64.dll'],n
 resources=set();deps=[];externals=set();artifact_count=0
 for asset in assets:
  d=json.loads((mod/'Custom'/asset/'build.json').read_text(encoding='utf8'))
  for e in d['artifacts']:
   p=mod/'Custom'/asset/e['path'];assert p.stat().st_size==e['size']
   assert sha(p)==sha(backup/'game/mods/AnimeModelReplacement/Custom'/asset/e['path'])
   if e.get('resource'):resources.add((e['resource']['type'],e['resource']['name']))
   artifact_count+=1
  for e in d.get('external_resources',[]):externals.add((e['key']['type'],e['key']['name']))
  for e in d.get('resources',[]):
   if isinstance(e,dict):
    for dep in e.get('dependencies',[]):
     k=dep.get('key',dep);deps.append((k['type'],k['name']))
 assert set(deps)<=resources|externals
 assert externals<={('material','content/parent_materials/substance_basic'),('material','#ID[cfe7f61e8e475a1a]')},externals
 lua_count=0;required=[]
 for existing in [False,True]:
  vm=LuaRuntime(unpack_returned_tuples=True)
  vm.globals().py_read=lambda p:(mod/(p.removeprefix('AnimeModelReplacement/')+'.lua')).read_text(encoding='utf-8-sig')
  vm.execute('''mods={};registrations={};CLASS={PortraitUI={},MissionIntroView={},PlayerVisibilityExtension={},PlayerUnitVisualLoadoutExtension={},PlayerHuskVisualLoadoutExtension={},HudElementPlayerPanelBase={}}
  function fassert(ok,msg)assert(ok,msg)end
  function new_mod(id,spec)
    assert(not mods[id],id);local m={values={}}
    function m:io_dofile(path)return assert(loadstring(py_read(path)))()end
    function m:localize(k)return k end
    function m:get(k)return self.values[k]end
    function m:set(k,v)self.values[k]=v end
    function m:is_enabled()return true end
    function m:command(...)end
    function m:hook(...)end
    function m:hook_safe(...)end
    function m:echo(...)end
    function m:error(...)error('unexpected package error')end
    mods[id]=m;registrations[id]=spec
  end
  function get_mod(id)return mods[id]end''')
  if existing:vm.execute('mods.CustomAssets={external=true}')
  descriptor=vm.execute((mod/'AnimeModelReplacement.mod').read_text(encoding='utf8'))
  descriptor.run()
  descriptor.run()
  descriptor.run()
  expected={'AnimeModelReplacement','ModelReplacementRegistry',*PROVIDERS}
  if not existing:expected.add('CustomAssets')
  assert set(vm.globals().registrations.keys())==expected
  if existing:assert vm.globals().mods.CustomAssets.external
  if not existing:
   parse=vm.eval('function(s)local f,e=loadstring(s);return f~=nil,e end')
   for p in mod.rglob('*'):
    if p.suffix in ['.lua','.mod']:
     ok,err=parse(p.read_text(encoding='utf-8-sig'));assert ok,(str(p),err);lua_count+=1
   for module,spec in vm.globals().registrations.items():
    for field in ['mod_script','mod_data','mod_localization']:
     assert (mod/(spec[field].removeprefix('AnimeModelReplacement/')+'.lua')).is_file()
   data=vm.execute((mod/'scripts/mods/AnimeModelReplacement/AnimeModelReplacement_data.lua').read_text(encoding='utf8'))
   widgets={}
   def collect(ws):
    for _,w in ws.items():
     if w.setting_id:
      widgets[w.setting_id]=w
      if w.default_value is not None:vm.globals().mods.AnimeModelReplacement['values'][w.setting_id]=w.default_value
     if w.sub_widgets:collect(w.sub_widgets)
   collect(data.options.widgets)
   assert set(widgets)=={'class_models','common_settings','model_enabled','replace_teammates','first_person_arms','menu_previews','model_options_model','laiwanting_outfit',*['model_'+c for c in ['veteran','zealot','psyker','adamant','broker','cryptic']]},list(widgets)
   outfit=widgets['laiwanting_outfit'];assert [v.value for _,v in outfit.options.items()]==['original','simple']
   for w in widgets.values():
    if w.type=='dropdown':assert len(w.options)>=2
   options=widgets['model_options_model'];assert {o.value for _,o in options.options.items()}==PROVIDERS|{'none'}
   for _,o in options.options.items():assert bool(len(o.show_widgets))==(o.value=='LaiwantingReplacement')
   vm.execute((mod/'scripts/mods/AnimeModelReplacement/AnimeModelReplacement.lua').read_text(encoding='utf8'))
   manager=vm.globals().mods.AnimeModelReplacement
   for c in ['veteran','zealot','psyker','adamant','broker','cryptic']:
    for provider in PROVIDERS:
     manager['values']['model_'+c]=provider
     assert manager.should_replace(provider,c,'body','human')
     assert manager.should_replace(provider,c,'preview','human')
     assert not manager.should_replace(provider,'ogryn','body','ogryn')
   catalog=plain(vm.execute((mod/'scripts/mods/AnimeModelReplacement/costume_catalog.lua').read_text(encoding='utf8')))
   for provider,c in catalog.items():
    assert all(e['asset'] in KEEP and e['variants']==1 for e in c['outfits'])
    assert len(c['outfits'])==(2 if provider=='LaiwantingReplacement' else 1)
    for e in c['outfits']:
     for suffix in ['', '_arms']:assert e['asset']+suffix in assets
     if e['id']!='original':
      for suffix in ['_jiggle_bones.lua','_proportion_bones.lua']:
       assert (mod/'scripts/mods'/provider/(e['asset']+suffix)).is_file()
 for p in (mod/'scripts').rglob('*.lua'):
  code=p.read_text(encoding='utf8')
  assert not any(k in code for k in ['DaniyaReplacement','AimisiReplacement','QianxiaReplacement','AnimeModelReplacement:qianxia']),p
  for path in re.findall(r':io_dofile\("([^"\n]+)"\)',code):
   assert (mod/(path.removeprefix('AnimeModelReplacement/')+'.lua')).is_file(),(p,path)
 equipment=audit(mod)
 assert len(equipment)==16 and all(x.get('retired_weapon_orphan')==False for x in equipment)
 print('STATIC_OK',len(assets),artifact_count,lua_count,flush=True)
 fixture=ROOT/'tools/model-work/package-tests'/('endfield_clean_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
 fixture.mkdir(parents=True,exist_ok=False)
 live_before=sha(GAME/'bundle/bundle_database.data')
 print('FIXTURE_COPY',fixture,flush=True)
 shutil.copytree(backup/'game/bundle',fixture/'bundle')
 for rel in ['tools/custom-assets-patcher.exe','tools/custom-assets-state.json','tools/custom-assets-manifest.json','tools/custom-assets-manifest.lua']:
  p=fixture/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(backup/'game'/rel,p)
 (fixture/'binaries').mkdir(exist_ok=True)
 shutil.copy2(GAME/'binaries/oo2core_9_win64.dll',fixture/'binaries/oo2core_9_win64.dll')
 (fixture/'binaries/Darktide.exe').write_bytes(b'not executable; isolated installer fixture')
 (fixture/'mods').mkdir(exist_ok=True)
 old=json.loads((fixture/'tools/custom-assets-state.json').read_text())
 cleanup=subprocess.run([str(fixture/'tools/custom-assets-patcher.exe')],cwd=fixture,capture_output=True)
 log=cleanup.stdout.decode(errors='replace')+cleanup.stderr.decode(errors='replace')
 write(fixture/'cleanup.log',log)
 assert cleanup.returncode==0,log
 current=json.loads((fixture/'tools/custom-assets-state.json').read_text())
 assert current['asset_count']==0 and current['resource_count']==0,current
 assert not any((fixture/'bundle'/n).exists() for n in old['bundles'])
 assert not any((fixture/'bundle'/n).exists() for n in old['streams'])
 clean_db=sha(fixture/'bundle/bundle_database.data')
 print('CLEAN_UNINSTALL_OK',len(old['bundles']),len(old['streams']),flush=True)
 fresh=fixture/'mods/AnimeModelReplacement';shutil.copytree(mod,fresh)
 command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(fresh/'_setup/install.ps1')]
 logs=[]
 duplicate_order=None
 duplicate_expected=None
 for i in range(4):
  result=subprocess.run(command,cwd=fixture,capture_output=True)
  log=result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace');logs.append(log)
  write(fixture/('install_'+str(i+1)+'.log'),log)
  assert result.returncode==0,log
  assert '34 asset folder(s): 34 ready, 0 skipped' in log,log
  assert '0 bundle(s), 0 stream(s) and no database change' in log,log
  order=fixture/'mods/mod_load_order.txt'
  assert order.read_text(encoding='utf-8-sig').splitlines().count('AnimeModelReplacement')==1
  if duplicate_expected is not None:
   assert order.read_bytes()==duplicate_expected,'Installer changed unrelated load-order bytes'
   assert ('Duplicate model load entries removed: '+str(1 if i==1 else 3 if i==2 else 0)) in log,log
  registered=json.loads((fixture/'tools/custom-assets-manifest.json').read_text())
  assert len(registered['assets'])==34
  if i==0:
   incident=json.loads((ROOT/'tools/model-work/share_hotfix_latest.json').read_text(encoding='utf8'))
   duplicate_order=(pathlib.Path(incident['backup'])/'game/mods/mod_load_order.txt').read_bytes()
   lines=duplicate_order.splitlines(keepends=True);seen=False;kept=[]
   for line in lines:
    if line.strip()==b'AnimeModelReplacement':
     if seen:continue
     seen=True
    kept.append(line)
   assert sum(line.strip()==b'AnimeModelReplacement' for line in lines)==2
   duplicate_expected=b''.join(kept)
   order.write_bytes(duplicate_order)
   loader=fixture/'binaries/mod_loader';loader.write_text(loader.read_text(encoding='utf8')+'\n-- preserve loader sentinel\n',encoding='utf8')
  elif i==1:
   duplicate_expected=b'-- sentinel\r\nOtherMod\nAnimeModelReplacement\r\n--AnimeModelReplacement\nOtherMod2\n'
   order.write_bytes(duplicate_expected+b'  AnimeModelReplacement  \r\nAnimeModelReplacement -- duplicate\nanimemodelreplacement\r\n')
  print('INSTALL_OK',i+1,flush=True)
 assert 'OtherMod' in order.read_text(encoding='utf8')
 assert '-- preserve loader sentinel' in (fixture/'binaries/mod_loader').read_text(encoding='utf8')
 assert sha(GAME/'bundle/bundle_database.data')==live_before
 report={'archive':str(archive),'archive_sha256':sha(archive),'characters':16,'outfits':17,'custom_asset_folders':34,'artifact_files_verified':artifact_count,'lua_files_parsed':lua_count,'equipment_provider_checks':len(equipment),'resource_dependencies_closed':True,'all_six_human_class_routes':True,'ogryn_excluded':True,'only_laiwanting_has_optional_skin':True,'single_option_dropdowns_absent':True,'old_77_asset_cleanup_tested':True,'old_registered_bundles_removed':len(old['bundles']),'old_registered_streams_removed':len(old['streams']),'clean_database_sha256':clean_db,'fresh_install_passed':True,'repeat_install_passed':True,'descriptor_repeated_three_times_safe':True,'actual_duplicate_load_order_replay_passed':True,'whitespace_comments_and_case_duplicates_removed':True,'four_installer_runs_passed':True,'preserves_other_load_entries_and_framework':True,'live_game_database_unchanged':True,'fixture':str(fixture),'gameplay_verified':False}
 reportpath=archive.with_name(archive.stem+'_validation.json');write(reportpath,json.dumps(report,ensure_ascii=False,indent=2))
 state.update({'validated':True,'validation':str(reportpath),'fixture':str(fixture)})
 write(statepath,json.dumps(state,ensure_ascii=False,indent=2))
 print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
