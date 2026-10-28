"""Verify installed hashes, provider routes and registered new resource identities."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
GAME = Path('<DARKTIDE_GAME>')
MOD = GAME / 'mods/AnimeModelReplacement'
OUT = ROOT / 'tools/model-work/endfield_batch'
sys.path.insert(0, str(ROOT / 'tools/model-work/python-deps'))
from lupa.luajit21 import LuaRuntime
from endfield_wave3 import PROFILES


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    deployment = json.loads((OUT / 'wave3_deployment_latest.json').read_text(encoding='utf-8-sig'))
    for row in deployment['files']:
        relative = row['path']
        expected = row['sha256'].lower()
        assert sha(ROOT / relative) == expected, ('source_changed', relative)
        assert sha(MOD / relative) == expected, ('installed_mismatch', relative)
    global_manifest = json.loads((GAME / 'tools/custom-assets-manifest.json').read_text(encoding='utf-8-sig'))
    assets = {a['logical_id']: a for a in global_manifest['assets']}
    resource_checks = {}
    for key in PROFILES:
        for asset in (key, key + '_arms'):
            folder = MOD / 'Custom' / asset
            build = json.loads((folder / 'build.json').read_text(encoding='utf-8-sig'))
            registered = assets['AnimeModelReplacement:' + asset]
            identities = []
            for artifact in build['artifacts']:
                file = folder / artifact['path']
                assert file.stat().st_size == artifact['size'], file
                if artifact['role'] != 'primary':
                    continue
                rel = file.relative_to(GAME).as_posix()
                matches = [r for r in registered['resources'] if r['source'].replace('\\', '/') == rel]
                assert len(matches) == 1, (asset, rel)
                r = matches[0]
                assert r['engine_type'] == artifact['resource']['type'], (file, r)
                name_hash = struct.unpack_from('<Q', file.read_bytes(), 8)[0]
                assert r['name'] in (artifact['resource']['name'], f'#ID[{name_hash:016x}]'), (file, r)
                identities.append(artifact['resource']['name'])
            if asset == key:
                assert f'content/mods/{key}/{key}_portrait' in identities, key
            resource_checks[asset] = {'registered_primary_resources': len(identities),
                                      'artifact_count': len(build['artifacts']),
                                      'unit_sha256': sha(folder / (asset + '.unit'))}

    # Execute actual installed controller with only engine/DMF calls mocked.
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''mods={};registered={};settings={model_enabled=true,menu_previews=true}
      CLASS={MissionIntroView={},PlayerVisibilityExtension={},PlayerUnitVisualLoadoutExtension={},
       PlayerHuskVisualLoadoutExtension={},PortraitUI={},HudElementPlayerPanelBase={}}
      fassert=assert
      function new_mod(id,params)assert(not registered[id]);registered[id]=params end
      function get_mod(id)
       if not mods[id]then mods[id]={localize=function(_,k)return k end,
         get=function(_,k)return settings[k]end,set=function(_,k,v)settings[k]=v end,
         command=function()end,hook=function()end,hook_safe=function()end,
         is_enabled=function()return true end}end
       return mods[id]
      end''')
    def load_mod(_, name):
        assert name.startswith('AnimeModelReplacement/'), name
        path = MOD / (name.removeprefix('AnimeModelReplacement/') + '.lua')
        assert path.resolve().is_relative_to(MOD.resolve()), path
        return lua.execute(path.read_text(encoding='utf-8-sig'))
    shared = lua.globals().get_mod('AnimeModelReplacement')
    shared.io_dofile = load_mod
    lua.execute((MOD / 'AnimeModelReplacement.mod').read_text(encoding='utf-8-sig')).run()
    definitions = lua.execute((MOD / 'scripts/mods/AnimeModelReplacement/model_definitions.lua').read_text(encoding='utf-8-sig'))
    data = lua.execute((MOD / 'scripts/mods/AnimeModelReplacement/AnimeModelReplacement_data.lua').read_text(encoding='utf-8-sig'))
    lua.execute((MOD / 'scripts/mods/AnimeModelReplacement/AnimeModelReplacement.lua').read_text(encoding='utf-8-sig'))
    assert len(definitions.models) == 20
    settings = lua.globals().settings
    routes = 0
    for key, profile in PROFILES.items():
        assert lua.globals().registered[profile['provider']], key
        for _, cls in definitions.classes.items():
            settings['model_' + cls.id] = profile['provider']
            for breed in ('human', 'cryptic'):
                for surface in ('body', 'arms', 'preview'):
                    assert shared.should_replace(profile['provider'], cls.id, surface, breed), (key, cls.id, breed, surface)
                    routes += 1
            assert not shared.should_replace(profile['provider'], cls.id, 'body', 'ogryn')
    assert len(data.options.widgets[1].sub_widgets) == 6
    assert all(len(v.options) == 20 for _, v in data.options.widgets[1].sub_widgets.items())
    compile_lua = lua.eval('function(s)local f,e=loadstring(s);return f~=nil,e end')
    files = list((MOD / 'scripts/mods').rglob('*.lua'))
    for path in files:
        ok, error = compile_lua(path.read_text(encoding='utf-8-sig'))
        assert ok, (path, error)
    load_order = (GAME / 'mods/mod_load_order.txt').read_text(encoding='utf-8-sig').splitlines()
    assert sum(line.strip().split('--', 1)[0].strip() == 'AnimeModelReplacement' for line in load_order) == 1

    # Run the existing HUD callback suite against the actual installed module.
    path = ROOT / 'tools/model-work/test_screenshot_portraits.py'
    code = path.read_text(encoding='utf-8')
    code = code.replace("ROOT = Path(__file__).resolve().parents[2]", "ROOT = Path(" + repr(str(MOD)) + ")")
    code = code.replace("str(ROOT / 'tools/model-work/python-deps')", repr(str(ROOT / 'tools/model-work/python-deps')))
    code = code.replace("(ROOT / 'tools/model-work/distribution_fix/screenshot_portrait_checks.json')",
                        "Path(" + repr(str(OUT / 'wave3_installed_portrait_checks.json')) + ")")
    exec(compile(code, str(path), 'exec'), {'__name__': '__main__', '__file__': str(path)})

    suites = {}
    for name in ('test_preview_scene_ownership', 'test_native_equipment_lifecycle'):
        output = OUT / ('wave3_installed_' + name.removeprefix('test_') + '.json')
        process = subprocess.run([sys.executable, str(ROOT / 'tools/model-work' / (name + '.py')),
                                  '--root', str(MOD), '--output', str(output)],
                                 cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert process.returncode == 0, process.stdout + process.stderr
        suites[name] = json.loads(output.read_text(encoding='utf-8'))
        print(process.stdout.strip())
    result = {'game_mod': str(MOD), 'verified_copied_files': len(deployment['files']),
              'registered_resources': resource_checks, 'class_surface_breed_routes': routes,
              'lua_files_parsed': len(files), 'models': len(definitions.models) - 1,
              'one_enabled_load_order_entry': True, 'installed_lifecycle_suites': suites,
              'game_launched': False, 'in_game_validation': False}
    (OUT / 'wave3_deployment_verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('WAVE3_INSTALLED_VERIFIED', len(deployment['files']), 'files', len(resource_checks), 'assets', routes, 'routes')


if __name__ == '__main__':
    main()
