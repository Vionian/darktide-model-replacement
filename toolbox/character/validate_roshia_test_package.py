"""Validate the isolated distribution without importing another model mod."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/model-work/python-deps'))
from lupa.luajit21 import LuaRuntime

archive = Path(sys.argv[1]).resolve()
package = archive.with_suffix('')
report = {'archive': archive.name}
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    manifest = json.loads(z.read('roshia_test_manifest.json'))
    assert len(z.namelist()) == len(manifest['files']) + 1
    for entry in manifest['files']:
        content = z.read(entry['path'])
        assert len(content) == entry['size']
        assert hashlib.sha256(content).hexdigest() == entry['sha256']
    names = z.namelist()
    for excluded in ('qianxia', 'daniya', 'aimisi', 'bundle_database.data', 'custom-assets-state.json', 'custom-assets-manifest.lua', 'user_settings.config'):
        assert not any(excluded in n.lower() for n in names), excluded
report['zip_hashes_and_crc_verified'] = len(manifest['files'])

mod = package / 'mods/AnimeModelReplacement'
assets = sorted(p.name for p in (mod / 'Custom').iterdir())
assert assets == ['roshia', 'roshia_arms']
report['assets'] = assets
resource_count = 0
for asset in assets:
    base = mod / 'Custom' / asset
    m = json.loads((base / 'build.json').read_text(encoding='utf-8'))
    for artifact in m['artifacts']:
        assert (base / artifact['path']).stat().st_size == artifact['size']
        resource_count += 1
    for path in m.get('resources', []):
        if isinstance(path, str):
            assert (base / path).is_file(), path
    assert all(e['key']['name'] == 'content/parent_materials/substance_basic' for e in m['external_resources'])
report['compiled_artifacts_verified'] = resource_count

lua = LuaRuntime(unpack_returned_tuples=True)


def read_mod(relative):
    path = package / 'mods' / relative
    assert path.is_file(), relative
    return path.read_text(encoding='utf-8-sig')


lua.globals().py_read = read_mod
lua.execute('''
mods = {}; registrations = {}
function fassert(ok,msg) assert(ok,msg) end
function new_mod(id,spec)
    assert(not mods[id],id)
    local m={values={}}
    function m:io_dofile(path) return assert(loadstring(py_read(path..".lua")))() end
    function m:localize(key) return key end
    function m:get(key) return self.values[key] end
    function m:set(key,value) self.values[key]=value end
    function m:is_enabled() return true end
    function m:command(name,description,fn) end
    function m:echo(...) end
    function m:error(...) error("unexpected package error") end
    mods[id]=m; registrations[id]=spec
end
function get_mod(id) return mods[id] end
''')
descriptor = lua.execute((mod / 'AnimeModelReplacement.mod').read_text(encoding='utf-8'))
descriptor.run()
registered = sorted(lua.globals().registrations.keys())
assert registered == sorted(['CustomAssets', 'ModelReplacementRegistry', 'AnimeModelReplacement', 'RoshiaReplacement'])
report['registered_modules'] = registered
lua_count = 0
for path in (package / 'mods').rglob('*'):
    if path.suffix in ('.lua', '.mod'):
        text = path.read_text(encoding='utf-8-sig')
        ok, error = lua.eval('function(s) local f,e=loadstring(s);return f~=nil,e end')(text)
        assert ok, (str(path), error)
        lua_count += 1
for module, spec in lua.globals().registrations.items():
    for field in ('mod_script', 'mod_data', 'mod_localization'):
        text = read_mod(spec[field] + '.lua')
        if field != 'mod_script':
            value = lua.execute(text)
            assert value is not None
            if module == 'AnimeModelReplacement' and field == 'mod_data':
                def defaults(widgets):
                    for _, widget in widgets.items():
                        if widget.setting_id and widget.default_value is not None:
                            lua.globals().mods[module]['values'][widget.setting_id] = widget.default_value
                        if widget.sub_widgets:
                            defaults(widget.sub_widgets)
                defaults(value.options.widgets)
for path in (mod / 'scripts').rglob('*.lua'):
    text = path.read_text(encoding='utf-8')
    for relative in re.findall(r':io_dofile\("([^"\n]+)"\)', text):
        read_mod(relative + '.lua')
    assert not any(n in text for n in ('DaniyaReplacement', 'QianxiaReplacement', 'AimisiReplacement')), path
lua.execute(read_mod('AnimeModelReplacement/scripts/mods/AnimeModelReplacement/AnimeModelReplacement.lua'))
manager = lua.globals().mods['AnimeModelReplacement']
classes = ['veteran', 'zealot', 'psyker', 'adamant', 'broker', 'cryptic']
for name in classes:
    assert manager.model_for_class(name) == 'RoshiaReplacement'
    assert manager.should_replace('RoshiaReplacement', name, 'body', 'human')
    assert manager.should_replace('RoshiaReplacement', name, 'preview', 'human')
assert not manager.should_replace('RoshiaReplacement', 'ogryn', 'body', 'ogryn')
assert not manager.model_supports_breed('RoshiaReplacement', 'ogryn')
report['lua_sources_parsed'] = lua_count
report['fresh_install_default_classes'] = classes
report['ogryn_excluded'] = True
result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(package / 'tools/roshia_test_install.ps1'), '-CheckOnly'], capture_output=True)
assert result.returncode == 0, result.stdout + result.stderr
report['powershell_check_only'] = result.stdout.decode(errors='replace').strip()

# A separate scratch root contains the real game's database only for a dry
# run. Never put this machine-specific database into the distribution ZIP.
smoke = ROOT / 'tools/model-work/roshia' / (archive.stem + '_isolated_smoke_' + str(time.time_ns()))
assert not smoke.exists()
assert smoke.resolve().is_relative_to(ROOT / 'tools/model-work/roshia')
shutil.copytree(package, smoke)
game = Path(r'<DARKTIDE_GAME>')
shutil.copy2(game / 'bundle/bundle_database.data', smoke / 'bundle/bundle_database.data')
shutil.copy2(game / 'bundle/a2bbcc3451758add', smoke / 'bundle/a2bbcc3451758add')
shutil.copy2(game / 'bundle/9ba626afa44a3aa3', smoke / 'bundle/9ba626afa44a3aa3')
shutil.copy2(game / 'binaries/oo2core_9_win64.dll', smoke / 'binaries/oo2core_9_win64.dll')
result = subprocess.run([str(smoke / 'tools/custom-assets-patcher.exe'), '--dry-run'], cwd=smoke, capture_output=True)
output = result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace')
(archive.parent / (archive.stem + '_isolated_patcher.log')).write_text(output, encoding='utf-8')
assert result.returncode == 0, output
assert '2 asset folder(s): 2 ready, 0 skipped' in output, output
report['isolated_patcher_dry_run'] = output.strip()
report['game_launched'] = False
path = archive.parent / (archive.stem + '_validation.json')
path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=True, indent=2))
