import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/model-work/python-deps'))
from lupa.luajit21 import LuaRuntime

archive = Path(sys.argv[1]).resolve()
package = archive.with_suffix('') / 'AnimeModelReplacement'
previous = ROOT / 'releases/Roshia_AnimeModelReplacement_FullTest_20261018_184741/mods/AnimeModelReplacement'
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert {p.split('/')[0] for p in z.namelist()} == {'AnimeModelReplacement'}
    manifest = json.loads(z.read('AnimeModelReplacement/_setup/package_manifest.json'))
    assert len(manifest['files']) + 1 == len(z.namelist())
    for entry in manifest['files']:
        data = z.read('AnimeModelReplacement/' + entry['path'])
        assert len(data) == entry['size']
        assert hashlib.sha256(data).hexdigest() == entry['sha256']
    assert not any(any(n in p.lower() for n in ('qianxia', 'daniya', 'aimisi', 'bundle_database.data', 'user_settings.config')) for p in z.namelist())
count = 0
for asset in ('roshia', 'roshia_arms'):
    base = package / 'Custom' / asset
    data = json.loads((base / 'build.json').read_text(encoding='utf-8'))
    for entry in data['artifacts']:
        assert (base / entry['path']).read_bytes() == (previous / 'Custom' / asset / entry['path']).read_bytes()
        count += 1
for p in (package / 'scripts').rglob('*.lua'):
    assert p.read_bytes() == (previous / p.relative_to(package)).read_bytes(), p
for preexisting in (False, True):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
    registered={}; existing={}
    function get_mod(id) return existing[id] end
    function fassert(ok,msg) assert(ok,msg) end
    function new_mod(id,spec) assert(not existing[id],id);registered[id]=spec;existing[id]={} end
    ''')
    if preexisting:
        lua.execute('existing.CustomAssets={external=true}')
    descriptor = lua.execute((package / 'AnimeModelReplacement.mod').read_text(encoding='utf-8'))
    descriptor.run()
    expected = ['AnimeModelReplacement', 'ModelReplacementRegistry', 'RoshiaReplacement']
    if not preexisting:
        expected.append('CustomAssets')
    assert sorted(lua.globals().registered.keys()) == sorted(expected)
lua_count = 0
for p in package.rglob('*'):
    if p.suffix in ('.lua', '.mod'):
        ok, error = lua.eval('function(s) local f,e=loadstring(s);return f~=nil,e end')(p.read_text(encoding='utf-8-sig'))
        assert ok, (str(p), error)
        lua_count += 1
result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(package / '_setup/install.ps1'), '-CheckOnly'], capture_output=True)
assert result.returncode == 0, result.stdout + result.stderr

game = Path(r'<DARKTIDE_GAME>')
scratch = ROOT / 'tools/model-work/roshia' / (archive.stem + '_install_smoke_' + str(time.time_ns()))
assert not scratch.exists()
assert scratch.resolve().is_relative_to(ROOT / 'tools/model-work/roshia')
mod = scratch / 'mods/AnimeModelReplacement'
shutil.copytree(package, mod)
for relative in ('bundle/bundle_database.data', 'bundle/a2bbcc3451758add', 'bundle/9ba626afa44a3aa3', 'binaries/oo2core_9_win64.dll'):
    (scratch / relative).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(game / relative, scratch / relative)
(scratch / 'binaries/Darktide.exe').write_bytes(b'not executable; isolated installer fixture only')
before = hashlib.sha256((game / 'bundle/bundle_database.data').read_bytes()).hexdigest()
log = []
command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(mod / '_setup/install.ps1')]
for iteration in range(2):
    result = subprocess.run(command, capture_output=True)
    text = result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace')
    log.append(text)
    assert result.returncode == 0, text
    assert '2 asset folder(s): 2 ready, 0 skipped' in text, text
    assert '0 bundle(s), 0 stream(s) and no database change' in text, text
    order = scratch / 'mods/mod_load_order.txt'
    assert order.read_text(encoding='utf-8').splitlines().count('AnimeModelReplacement') == 1
    if iteration == 0:
        assert order.read_text(encoding='utf-8').splitlines() == ['AnimeModelReplacement']
        order.write_text('-- existing user entry\nOtherMod\nAnimeModelReplacement\n', encoding='utf-8')
        # Existing frameworks must not be replaced during the second install.
        loader = scratch / 'binaries/mod_loader'
        loader.write_text(loader.read_text(encoding='utf-8') + '\n-- preserve existing loader sentinel\n', encoding='utf-8')
assert order.read_text(encoding='utf-8').splitlines() == ['-- existing user entry', 'OtherMod', 'AnimeModelReplacement']
assert '-- preserve existing loader sentinel' in loader.read_text(encoding='utf-8')
for entry in manifest['files']:
    if entry['path'].startswith('_setup/payload/'):
        relative = entry['path'][len('_setup/payload/'):]
        assert (scratch / relative).is_file(), relative
assert hashlib.sha256((game / 'bundle/bundle_database.data').read_bytes()).hexdigest() == before
(archive.parent / (archive.stem + '_install_smoke.log')).write_text('\n\n'.join(log), encoding='utf-8')
report = {'zip': archive.name, 'top_level_folders': ['AnimeModelReplacement'], 'files_in_zip': len(manifest['files']) + 1,
          'compiled_artifacts_unchanged': count, 'runtime_lua_unchanged': True, 'lua_sources_parsed': lua_count,
          'external_custom_assets_api_reused': True, 'check_only_passed': True,
          'first_install_without_mod_loader_or_dmf': 'passed in isolated fixture',
          'repeat_install_no_duplicate_load_entry': True, 'existing_load_order_and_loader_preserved': True,
          'matched_plugin_and_patcher_installed': True, 'only_roshia_assets_registered': True,
          'final_pending_bundles': 0, 'final_pending_streams': 0,
          'live_game_database_unchanged': True, 'game_launched': False,
          'plugin_automatic_startup': 'documented upstream and present in existing installation logs; no game launch performed'}
(archive.parent / (archive.stem + '_validation.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=True, indent=2))
