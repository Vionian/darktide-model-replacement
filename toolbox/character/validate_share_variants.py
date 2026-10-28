"""Validate distribution closure, Lua boot and clean/repeat installs off-game."""
import argparse,pathlib,sys,json,hashlib,zipfile,re,shutil,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/model-work/python-deps'))
from lupa.luajit21 import LuaRuntime
from package_share_variants import ENDFIELD,WUWA,OUTFITS,sha,GAME
from test_preview_lifecycle import exercise
from test_native_equipment_lifecycle import audit

def validate(info):
    archive=pathlib.Path(info['zip']);package=pathlib.Path(info['folder'])/'AnimeModelReplacement'
    models={**ENDFIELD,**(WUWA if info['variant']=='all' else {})}
    providers={v[1] for v in models.values()};assets={a for key in models for a in (key,key+'_arms')}
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert {p.split('/')[0] for p in z.namelist()}=={'AnimeModelReplacement'}
        manifest=json.loads(z.read('AnimeModelReplacement/_setup/package_manifest.json'))
        if manifest.get('outfits'):
            assert manifest['outfits']=={key:list(value)for key,value in OUTFITS.items()}
            assets.update(a for values in OUTFITS.values()for key in values for a in (key,key+'_arms'))
        assert set(manifest['assets'])==assets
        assert len(z.namelist())==len(manifest['files'])+1
        for entry in manifest['files']:
            assert not pathlib.PurePosixPath(entry['path']).is_absolute() and '..' not in pathlib.PurePosixPath(entry['path']).parts
            data=z.read('AnimeModelReplacement/'+entry['path'])
            assert len(data)==entry['size'] and hashlib.sha256(data).hexdigest()==entry['sha256'],entry['path']
            assert data==(package/entry['path']).read_bytes(),('ZIP differs from tested staged file',entry['path'])
        for bad in ('bundle_database.data','user_settings.config','custom-assets-state.json','custom-assets-manifest.lua','Darktide.exe','oo2core_9_win64.dll'):
            assert not any(pathlib.PurePosixPath(n).name==bad for n in z.namelist()),bad
    assert {p.name for p in (package/'Custom').iterdir()}==assets
    assert {p.name for p in (package/'scripts/mods').iterdir()}=={'CustomAssets','ModelReplacementRegistry','AnimeModelReplacement',*providers}
    artifacts=0;resource_files=set();dependencies=[];externals=set()
    for asset in assets:
        folder=package/'Custom'/asset
        data=json.loads((folder/'build.json').read_text())
        for e in data['artifacts']:
            path=folder/e['path'];assert path.stat().st_size==e['size'] and sha(path)==sha(ROOT/'Custom'/asset/e['path'])
            artifacts+=1
            # The serialized resource key is authoritative.  Older Daniya
            # assets deliberately use the shared content/mods/daniya prefix,
            # so deriving names from the package folder rejects valid bundles.
            resource=e.get('resource')
            if resource:
                resource_files.add((resource['type'],resource['name']))
        for ext in data.get('external_resources',[]):
            k=ext['key'];externals.add((k['type'],k['name']))
        for res in data.get('resources',[]):
            if isinstance(res,dict):
                for dep in res.get('dependencies',[]):
                    key=dep.get('key',dep);dependencies.append((key['type'],key['name']))
    assert all(x in resource_files or x in externals for x in dependencies)
    assert externals<={('material','content/parent_materials/substance_basic'),('material','#ID[cfe7f61e8e475a1a]')},externals
    lua_count=0
    for existing in (False,True):
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.globals().py_read=lambda p:(package/(p.removeprefix('AnimeModelReplacement/')+'.lua')).read_text(encoding='utf-8-sig')
        lua.execute('''mods={};registrations={};CLASS={PortraitUI={},MissionIntroView={},PlayerVisibilityExtension={},PlayerUnitVisualLoadoutExtension={},PlayerHuskVisualLoadoutExtension={},HudElementPlayerPanelBase={}}
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
        if existing:lua.execute('mods.CustomAssets={external=true}')
        lua.execute((package/'AnimeModelReplacement.mod').read_text()).run()
        expected={'AnimeModelReplacement','ModelReplacementRegistry',*providers}
        if not existing:expected.add('CustomAssets')
        assert set(lua.globals().registrations.keys())==expected
        if existing:assert lua.globals().mods.CustomAssets.external
        else:
            for path in package.rglob('*'):
                if path.suffix in ('.lua','.mod'):
                    ok,err=lua.eval('function(s)local f,e=loadstring(s);return f~=nil,e end')(path.read_text(encoding='utf-8-sig'))
                    assert ok,(path,err);lua_count+=1
            for module,spec in lua.globals().registrations.items():
                for field in ('mod_script','mod_data','mod_localization'):
                    path=package/(spec[field].removeprefix('AnimeModelReplacement/')+'.lua');assert path.is_file()
                    if field!='mod_script':value=lua.execute(path.read_text(encoding='utf-8-sig'))
                    if module=='AnimeModelReplacement' and field=='mod_data':
                        def defaults(widgets):
                            for _,w in widgets.items():
                                if w.setting_id and w.default_value is not None:lua.globals().mods[module]['values'][w.setting_id]=w.default_value
                                if w.sub_widgets:defaults(w.sub_widgets)
                        defaults(value.options.widgets)
                        if info['variant']=='endfield':
                            def collect(widgets):
                                found={}
                                for _,w in widgets.items():
                                    if w.setting_id:found[w.setting_id]=w
                                    if w.sub_widgets:found.update(collect(w.sub_widgets))
                                return found
                            widgets=collect(value.options.widgets)
                            classes=[w.setting_id for _,w in widgets['class_models'].sub_widgets.items()]
                            assert classes==['model_veteran','model_zealot','model_psyker','model_adamant','model_broker'],classes
                            assert 'model_cryptic' not in widgets
                            forbidden_options=('switch_model_keybind','model_variant')
                            if not manifest.get('outfits'):forbidden_options+=('model_options_model',)
                            for forbidden in forbidden_options:
                                assert forbidden not in widgets,forbidden
                            if manifest.get('outfits'):
                                assert widgets['si_outfit'].default_value=='original'
                                assert [o.value for _,o in widgets['si_outfit'].options.items()]==['original','ink_mist']
                                options=widgets['model_options_model']
                                assert len(options.sub_widgets)==1 and options.sub_widgets[1].setting_id=='si_outfit'
                                for _,o in options.options.items():
                                    if o.value=='SiReplacement':assert list(o.show_widgets.values())==[1]
                            assert [key for key,w in widgets.items() if w.type=='keybind']==['toggle_keybind']
                            assert widgets['toggle_keybind'].function_name=='toggle_models'
            lua.execute((package/'scripts/mods/AnimeModelReplacement/AnimeModelReplacement.lua').read_text())
            manager=lua.globals().mods.AnimeModelReplacement
            for cls in ('veteran','zealot','psyker','adamant','broker','cryptic'):
                for provider in providers:
                    manager['values']['model_'+cls]=provider
                    assert manager.should_replace(provider,cls,'body','human')
                    assert manager.should_replace(provider,cls,'preview','human')
                    assert not manager.should_replace(provider,'ogryn','body','ogryn')
                    manager['values']['menu_previews']=False
                    assert not manager.should_replace(provider,cls,'preview','human')
                    manager['values']['menu_previews']=True
    for path in (package/'scripts').rglob('*.lua'):
        code=path.read_text(encoding='utf-8')
        for relative in re.findall(r':io_dofile\("([^"\n]+)"\)',code):
            assert relative.startswith('AnimeModelReplacement/')
            assert (package/(relative.removeprefix('AnimeModelReplacement/')+'.lua')).is_file(),relative
        if info['variant']=='endfield':
            assert 'AnimeModelReplacement:qianxia' not in code
            assert not any(n in code for n in ('DaniyaReplacement','AimisiReplacement','QianxiaReplacement')),path
    lifecycle=[exercise(package,p) for p in sorted(providers)]
    assert all(x['reentrant_teardown_orphans']==0 for x in lifecycle)
    equipment=audit(package);assert len(equipment)==13 and all(x.get('retired_weapon_orphan')==False for x in equipment),equipment
    print('STATIC_OK',info['variant'],len(manifest['files']),artifacts,lua_count,flush=True)
    scratch=ROOT/'tools/model-work/package-tests'/('share_'+info['variant']+'_'+str(time.time_ns()))
    assert not scratch.exists() and scratch.resolve().is_relative_to(ROOT/'tools/model-work/package-tests')
    mod=scratch/'mods/AnimeModelReplacement';shutil.copytree(package,mod)
    before=sha(GAME/'bundle/bundle_database.data')
    for relative in ('bundle/bundle_database.data','bundle/a2bbcc3451758add','bundle/9ba626afa44a3aa3','binaries/oo2core_9_win64.dll'):
        (scratch/relative).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(GAME/relative,scratch/relative)
    (scratch/'binaries/Darktide.exe').write_bytes(b'not executable; isolated installer fixture')
    command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(mod/'_setup/install.ps1')]
    logs=[]
    for iteration in range(2):
        process=subprocess.run(command,capture_output=True)
        output=process.stdout.decode(errors='replace')+process.stderr.decode(errors='replace');logs.append(output)
        assert process.returncode==0,output
        assert f'{len(assets)} asset folder(s): {len(assets)} ready, 0 skipped' in output,output
        assert '0 bundle(s), 0 stream(s) and no database change' in output,output
        order=scratch/'mods/mod_load_order.txt';assert order.read_text(encoding='utf-8').splitlines().count('AnimeModelReplacement')==1
        if iteration==0:
            order.write_text('-- preserve existing entry\nOtherMod\nAnimeModelReplacement\n',encoding='utf-8')
            loader=scratch/'binaries/mod_loader';loader.write_text(loader.read_text(encoding='utf-8')+'\n-- preserve loader sentinel\n',encoding='utf-8')
    assert 'OtherMod' in order.read_text(encoding='utf-8')
    assert '-- preserve loader sentinel' in loader.read_text(encoding='utf-8')
    assert sha(GAME/'bundle/bundle_database.data')==before
    report={'archive':str(archive),'sha256':sha(archive),'files':len(manifest['files'])+1,'assets':sorted(assets),
       'artifacts_verified':artifacts,'lua_parsed':lua_count,'lifecycle_provider_checks':len(lifecycle),
       'native_equipment_provider_checks':len(equipment),'six_human_class_routes':True,'ogryn_excluded':True,
       'external_custom_assets_reused':True,'fresh_install_no_frameworks':True,'repeat_install_preserves_existing_files':True,
       'isolated_ready_assets':len(assets),'final_pending_bundle_changes':0,'live_database_unchanged':True,
       'game_launched':False,'scratch_fixture':str(scratch)}
    if info['variant']=='endfield':
        report['visible_class_dropdowns']=['veteran','zealot','psyker','adamant','broker']
        report['skitarius_dropdown_absent']=True
        report['daniya_shortcut_absent']=True
    archive.with_name(archive.stem+'_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    archive.with_name(archive.stem+'_install_smoke.log').write_text('\n\n'.join(logs),encoding='utf-8')
    print('VALIDATED',info['variant'],len(assets),flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--variant',choices=('endfield','all','both'),default='both')
    args=parser.parse_args()
    results=[validate(info) for info in json.loads((ROOT/'releases/share_variants_latest.json').read_text())
             if args.variant=='both' or info['variant']==args.variant]
    assert results,'No matching share package'
    output=ROOT/'tools/model-work/distribution_fix/share_validation.json'
    previous=json.loads(output.read_text(encoding='utf-8')) if output.exists() else []
    updated={pathlib.Path(row['archive']).name.split('_ModsDrop_')[0]:row for row in previous+results}
    output.write_text(json.dumps(list(updated.values()),ensure_ascii=False,indent=2),encoding='utf-8')
