"""Check five-character archive and perform clean/repeat installs in a scratch game."""
import pathlib,sys,json,hashlib,zipfile,re,shutil,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/model-work/python-deps'))
from lupa.luajit21 import LuaRuntime
latest=json.loads((ROOT/'releases/endfield_five_latest.json').read_text(encoding='utf-8'))
archive=pathlib.Path(latest['zip']);package=pathlib.Path(latest['folder'])/'AnimeModelReplacement'
models={'roshia':'RoshiaReplacement','lizhiyan':'LizhiyanReplacement','endministrator_f':'EndministratorReplacement','si':'SiReplacement','typhoea':'TyphoeaReplacement'}
assets={a for k in models for a in (k,k+'_arms')}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with zipfile.ZipFile(archive)as z:
    assert z.testzip()is None
    assert {p.split('/')[0]for p in z.namelist()}=={'AnimeModelReplacement'}
    manifest=json.loads(z.read('AnimeModelReplacement/_setup/package_manifest.json'))
    assert set(manifest['assets'])==assets
    assert len(z.namelist())==len(manifest['files'])+1
    for entry in manifest['files']:
        data=z.read('AnimeModelReplacement/'+entry['path'])
        assert len(data)==entry['size'] and hashlib.sha256(data).hexdigest()==entry['sha256'],entry
    for bad in ('bundle_database.data','user_settings.config','custom-assets-state.json','custom-assets-manifest.lua','Darktide.exe','oo2core_9_win64.dll'):
        assert not any(pathlib.PurePosixPath(n).name==bad for n in z.namelist()),bad
assert {p.name for p in (package/'Custom').iterdir()}==assets
assert {p.name for p in (package/'scripts/mods').iterdir()}=={'CustomAssets','ModelReplacementRegistry','AnimeModelReplacement',*models.values()}
artifacts=0
for asset in assets:
    folder=package/'Custom'/asset
    data=json.loads((folder/'build.json').read_text(encoding='utf-8'))
    for e in data['artifacts']:
        p=folder/e['path'];assert p.stat().st_size==e['size']
        assert sha(p)==sha(ROOT/'Custom'/asset/e['path'])
        artifacts+=1
    assert all(e['key']['name'].startswith('content/parent_materials/')for e in data.get('external_resources',[]))
lua_count=0
for preexisting in (False,True):
    lua=LuaRuntime(unpack_returned_tuples=True)
    lua.globals().py_read=lambda p:(package/(p.removeprefix('AnimeModelReplacement/')+'.lua')).read_text(encoding='utf-8-sig')
    lua.execute('''mods={};registrations={}
    function fassert(ok,msg)assert(ok,msg)end
    function new_mod(id,spec)
      assert(not mods[id],id)
      local m={values={}}
      function m:io_dofile(path)return assert(loadstring(py_read(path)))()end
      function m:localize(key)return key end
      function m:get(key)return self.values[key]end
      function m:set(key,value)self.values[key]=value end
      function m:is_enabled()return true end
      function m:command(...)end
      function m:echo(...)end
      function m:error(...)error('unexpected package error')end
      mods[id]=m;registrations[id]=spec
    end
    function get_mod(id)return mods[id]end''')
    if preexisting:lua.execute('mods.CustomAssets={external=true}')
    desc=lua.execute((package/'AnimeModelReplacement.mod').read_text(encoding='utf-8'));desc.run()
    expected={'AnimeModelReplacement','ModelReplacementRegistry',*models.values()}
    if not preexisting:expected.add('CustomAssets')
    assert set(lua.globals().registrations.keys())==expected
    if preexisting:assert lua.globals().mods.CustomAssets.external
    if not preexisting:
        for path in package.rglob('*'):
            if path.suffix in ('.lua','.mod'):
                ok,error=lua.eval('function(s)local f,e=loadstring(s);return f~=nil,e end')(path.read_text(encoding='utf-8-sig'))
                assert ok,(path,error)
                lua_count+=1
        for module,spec in lua.globals().registrations.items():
            for field in ('mod_script','mod_data','mod_localization'):
                path=package/(spec[field].removeprefix('AnimeModelReplacement/')+'.lua');assert path.is_file()
                if field!='mod_script':value=lua.execute(path.read_text(encoding='utf-8-sig'))
                if module=='AnimeModelReplacement'and field=='mod_data':
                    def defaults(widgets):
                        for _,w in widgets.items():
                            if w.setting_id and w.default_value is not None:lua.globals().mods[module]['values'][w.setting_id]=w.default_value
                            if w.sub_widgets:defaults(w.sub_widgets)
                    defaults(value.options.widgets)
        lua.execute((package/'scripts/mods/AnimeModelReplacement/AnimeModelReplacement.lua').read_text(encoding='utf-8'))
        manager=lua.globals().mods.AnimeModelReplacement
        for cls in ('veteran','zealot','psyker','adamant','broker','cryptic'):
            assert manager.model_for_class(cls)=='RoshiaReplacement'
            for provider in models.values():
                manager['values']['model_'+cls]=provider
                assert manager.should_replace(provider,cls,'body','human')
                assert manager.should_replace(provider,cls,'preview','human')
                assert not manager.should_replace(provider,'ogryn','body','ogryn')
                manager['values']['menu_previews']=False
                assert not manager.should_replace(provider,cls,'preview','human')
                manager['values']['menu_previews']=True
for path in (package/'scripts').rglob('*.lua'):
    text=path.read_text(encoding='utf-8')
    for relative in re.findall(r':io_dofile\("([^"\n]+)"\)',text):
        assert relative.startswith('AnimeModelReplacement/')
        assert (package/(relative.removeprefix('AnimeModelReplacement/')+'.lua')).is_file(),relative
    assert 'AnimeModelReplacement:qianxia'not in text
    assert not any(n in text for n in ('DaniyaReplacement','AimisiReplacement','QianxiaReplacement')),path
check=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(package/'_setup/install.ps1'),'-CheckOnly'],capture_output=True)
assert check.returncode==0,check.stdout+check.stderr
print('ENDFIELD_PACKAGE_STATIC_OK',len(manifest['files']),artifacts,lua_count,flush=True)
GAME=pathlib.Path(r'<DARKTIDE_GAME>')
scratch=ROOT/'tools/model-work/package-tests'/('endfield_five_'+str(time.time_ns()))
assert not scratch.exists() and scratch.resolve().is_relative_to(ROOT/'tools/model-work/package-tests')
mod=scratch/'mods/AnimeModelReplacement';shutil.copytree(package,mod)
for relative in ('bundle/bundle_database.data','bundle/a2bbcc3451758add','bundle/9ba626afa44a3aa3','binaries/oo2core_9_win64.dll'):
    (scratch/relative).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(GAME/relative,scratch/relative)
(scratch/'binaries/Darktide.exe').write_bytes(b'not executable; isolated installer fixture')
before=sha(GAME/'bundle/bundle_database.data');logs=[]
command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(mod/'_setup/install.ps1')]
for iteration in range(2):
    result=subprocess.run(command,capture_output=True)
    output=result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace');logs.append(output)
    assert result.returncode==0,output
    assert '10 asset folder(s): 10 ready, 0 skipped'in output,output
    assert '0 bundle(s), 0 stream(s) and no database change'in output,output
    order=scratch/'mods/mod_load_order.txt'
    assert order.read_text(encoding='utf-8').splitlines().count('AnimeModelReplacement')==1
    if iteration==0:
        order.write_text('-- preserve existing entry\nOtherMod\nAnimeModelReplacement\n',encoding='utf-8')
        loader=scratch/'binaries/mod_loader';loader.write_text(loader.read_text(encoding='utf-8')+'\n-- preserve loader sentinel\n',encoding='utf-8')
assert 'OtherMod'in order.read_text(encoding='utf-8')
assert '-- preserve loader sentinel'in loader.read_text(encoding='utf-8')
assert sha(GAME/'bundle/bundle_database.data')==before
report={'archive':str(archive),'archive_sha256':sha(archive),'zip_files':len(manifest['files'])+1,
        'assets':sorted(assets),'compiled_artifacts_verified':artifacts,'lua_sources_parsed':lua_count,
        'six_human_classes_times_five_model_routes':True,'ogryn_excluded':True,'external_custom_assets_api_reused':True,
        'installer_check_only':True,'fresh_install_without_frameworks':True,'repeat_install_preserves_loader_and_load_order':True,
        'isolated_registered_asset_count':10,'final_pending_bundle_and_stream_changes':0,'live_database_unchanged':True,
        'game_launched':False,'scratch_fixture':str(scratch)}
archive.with_name(archive.stem+'_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
archive.with_name(archive.stem+'_install_smoke.log').write_text('\n\n'.join(logs),encoding='utf-8')
print('ENDFIELD_PACKAGE_VALIDATED',json.dumps(report,ensure_ascii=True),flush=True)
