"""Verify the complete upgraded package without modifying the installed game."""
from pathlib import Path
from collections import Counter
import hashlib, importlib.util, json, re, struct, subprocess, zlib, sys
ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT/'WeaponModelReplacement'
ASSET = MOD/'Custom/khravengger'
spec = importlib.util.spec_from_file_location('asset_hash', '<CHARACTER_WORKSPACE>/tools/bitsquid-addon/murmur/murmurhash64.py')
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
build = json.loads((ASSET/'build.json').read_text())
keys = {(r['key']['type'],r['key']['name']) for r in build['resources']}
assert len(keys) == len(build['resources']) == 278
external = {(r['key']['type'], r['key']['name']) for r in build['external_resources']}
assert len(external) == 6 and not keys.intersection(external)
def checked_file(info):
    p = ASSET/info['path']
    assert p.resolve().is_relative_to(ASSET.resolve())
    data = p.read_bytes()
    assert len(data) == info['size'], p
    if 'crc32' in info: assert f'{zlib.crc32(data):08x}' == info['crc32'], p
    return data
for r in build['resources']:
    key = r['key']; raw = checked_file(r['file'])
    assert struct.unpack_from('<QQ',raw) == (h.hash64(key['type']),h.hash64(key['name'])), key
    assert r['name_hash'] == f"{h.hash64(key['name']):016x}", key
    for d in r['dependencies']: assert (d['type'],d['name']) in keys or (d['type'],d['name']) in external, (key,d)
    if r.get('stream'): checked_file(r['stream']['file'])
assert all((r['type'],r['name']) in keys for r in build['roots'])
assert len(build['artifacts']) == 481
for a in build['artifacts']: checked_file(a)
native_binding_check=subprocess.run(['<BLENDER_EXE>',
    '-b','--python',str(ROOT/'tools/verify_weapon_material_bindings.py')],
    capture_output=True,text=True,encoding='utf-8',errors='replace',check=True)
assert 'NATIVE_WEAPON_MATERIAL_BINDINGS_OK' in native_binding_check.stdout
(ROOT/'build/wolf_material/native_binding_check.log').write_text(native_binding_check.stdout,encoding='utf-8')
charge_check=subprocess.run([sys.executable,str(ROOT/'tools/test_charge_render_safety.py'),str(MOD)],
    capture_output=True,text=True,encoding='utf-8',errors='replace',check=True)
assert 'CHARGE_RENDER_SAFETY_OK' in charge_check.stdout
(ROOT/'build/wolf_charge_crash/source_render_safety.log').write_text(charge_check.stdout,encoding='utf-8')
edge_check=subprocess.run(['<BLENDER_EXE>',
    '-b','--python',str(ROOT/'tools/verify_blade_edge.py')],
    capture_output=True,text=True,encoding='utf-8',errors='replace',check=True)
assert 'BLADE_EDGE_NATIVE_OK' in edge_check.stdout
(ROOT/'build/blade_edge/source_geometry_check.log').write_text(edge_check.stdout,encoding='utf-8')
edge_charge=subprocess.run([sys.executable,str(ROOT/'tools/verify_blade_charge.py'),str(MOD)],
    capture_output=True,text=True,encoding='utf-8',errors='replace',check=True)
assert 'BLADE_CHARGE_VERIFIED' in edge_charge.stdout
backup = ROOT/'edit-backups/20261026-221415/WeaponModelReplacement/Custom/khravengger'
base = json.loads((backup/'build.json').read_text())
for r in base['resources']:
    if r['key'] == {'type':'unit','name':'content/mods/weapon_model_replacement/khravengger'}:
        continue  # the UNIT now serializes the added charge-cover meshes
    if r['key']['type']=='particles' and r['key']['name'].rsplit('/',1)[1] in ('ice_charge_aura','ice_forcesword_2h_stage2','ice_forcesword_2h_stage2_loop'):
        continue  # 0.2.8 intentionally confines sustained charge to blade edges.
    for f in [r['file']] + ([r['stream']['file']] if r.get('stream') else []):
        assert (ASSET/f['path']).read_bytes() == (backup/f['path']).read_bytes(), f
units = {r['key']['name']:r for r in build['resources'] if r['key']['type']=='unit'}
unit_validation = {}
compiler = ROOT/'tools/compiler/DarktideGLBCompiler.exe'
for name in ('khravengger','langzhifei'):
    resource = 'content/mods/weapon_model_replacement/'+name
    assert resource in units
    result = subprocess.run([str(compiler),'--validate',str(ASSET/units[resource]['file']['path'])],check=True,capture_output=True,text=True)
    unit_validation[name] = result.stdout.strip() or 'valid'
sources = sorted(MOD.rglob('*.lua')) + [MOD/'WeaponModelReplacement.mod']
for p in sources: subprocess.run(['<LUAC_EXE>','-p',str(p)],check=True,capture_output=True)
for name in ('CustomAssets.lua','CustomAssets_data.lua','CustomAssets_localization.lua'):
    assert (MOD/'scripts/mods/CustomAssets'/name).read_bytes() == (Path('<CHARACTER_WORKSPACE>/scripts/mods/CustomAssets')/name).read_bytes()
tests = {}
for name, marker in [('test_runtime.lua','RUNTIME_TESTS_OK 24'),('test_upgrade.lua','UPGRADE_TESTS_OK 46'),
                     ('test_preview_lifecycle.lua','PREVIEW_LIFECYCLE_TESTS_OK 25')]:
    argument = MOD if name == 'test_preview_lifecycle.lua' else ROOT
    r = subprocess.run(['<LUA_EXE>',str(ROOT/'tools'/name),str(argument)],capture_output=True,text=True,check=True)
    assert marker in r.stdout
    (ROOT/'build'/name.replace('.lua','.log')).write_text(r.stdout,encoding='utf-8')
    tests[name] = int(marker.rsplit(' ',1)[1])
fx = [r for r in build['resources'] if r['key']['type']=='particles']
assert len(fx) == 30
readback = ROOT/'build/ice_fx/readback'; readback.mkdir(exist_ok=True)
expected = {n['name']:n['extras']['darktide_asset']['particles']['effect'] for n in json.loads((ROOT/'build/ice_fx/ice_effects.gltf').read_text())['nodes']}
expected.update({n['name']:n['extras']['darktide_asset']['particles']['effect'] for n in json.loads((ROOT/'build/wolf_violet/violet_effects.gltf').read_text())['nodes']})
fx_summary = []
for r in fx:
    name = r['key']['name'].rsplit('/',1)[1]; target = readback/(name+'.json')
    subprocess.run([str(ROOT/'tools/compiler/DarktideGLBCompiler.exe'),'--particles',str(ASSET/r['file']['path']),str(target)],check=True,capture_output=True)
    actual = json.loads(target.read_text()); source = expected[name]
    assert len(actual['systems']) == len(source['systems']), name
    assert len(actual.get('variables',[])) == len(source.get('variables',[])), name
    assert actual['life_time'] == source['life_time'], name
    for a,b in zip(actual.get('variables',[]),source.get('variables',[])):
        assert a['name']==b['name'], (name,a,b)
        if isinstance(a.get('value'),list):
            assert len(a['value'])==len(b['value']) and all(abs(x-y)<1e-5 for x,y in zip(a['value'],b['value'])), (name,a,b)
    fx_summary.append({'name':name,'systems':len(actual['systems']),'variables':len(actual.get('variables',[]))})
report = {'version':json.loads((MOD/'info.json').read_text(encoding='utf-8'))['version'],'date':'2026-10-28','resources':len(keys),'artifacts':len(build['artifacts']),
    'external_original_references':len(external),
    'resource_types':dict(Counter(r['key']['type'] for r in build['resources'])),
    'lua_sources_parsed':len(sources),'runtime_tests':tests,'total_tests':sum(tests.values()),
    'dependency_closure_complete':True,'native_wrapper_hash_and_crc_checks':True,
    'original_materials_textures_and_unrelated_particles_byte_unchanged':True,'custom_assets_api_byte_identical':True,
    'model_unit_validation':unit_validation,
    'supported_profiles':{'psyker_forcesword_1h':['langzhifei'],
        'psyker_force_greatsword_2h':['khravengger'],
        'zealot_relic_power_sword':['khravengger'],
        'classes':['veteran','zealot','psyker','adamant','broker','cryptic']},
    'particle_binary_readbacks':fx_summary, 'first_person_height_cm_default':3,
    'geometry':json.loads((ROOT/'build/blade_edge/geometry_audit.json').read_text()),
    'blade_charge':json.loads((ROOT/'build/blade_edge/charge_audit.json').read_text()),
    'textures':json.loads((ROOT/'build/texture_audit.json').read_text()),
    'wolf_pose_geometry':json.loads((ROOT/'build/force_sword_pose/geometry_audit.json').read_text()),
    'wolf_grip_alignment':json.loads((ROOT/'build/force_sword_pose/langzhifei_alignment.json').read_text()),
    'ice_effects':{k:(len(v) if k=='material_color_edits' else v) for k,v in json.loads((ROOT/'build/ice_fx/audit.json').read_text()).items()},
    'preview_crash_repair':json.loads((ROOT/'build/preview_crash_analysis.json').read_text(encoding='utf-8')),
    'historical_wolf_violet_effects_build':json.loads((ROOT/'build/wolf_violet/audit.json').read_text(encoding='utf-8')),
    'weapon_material_bindings':json.loads((ROOT/'build/wolf_material/native_binding_audit.json').read_text(encoding='utf-8')),
    'charge_renderer_repair':json.loads((ROOT/'build/wolf_charge_crash/render_safety_audit.json').read_text(encoding='utf-8')),
    'deployed_to_game':False,'upgrade_in_game_tested':False}
(MOD/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('geometry','textures','particle_binary_readbacks')},ensure_ascii=False,indent=2))
