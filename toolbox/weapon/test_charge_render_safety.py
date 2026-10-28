"""Verify the exact crashed render branch is unreachable in installed particles."""
from pathlib import Path
import copy,json,sys,subprocess,importlib.util,re,hashlib
from particle_render_safety import sanitize,blocked_material,BAD_SHADER
ROOT=Path(__file__).resolve().parents[1]
MOD=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'WeaponModelReplacement'
ASSET=MOD/'Custom/khravengger';OUT=ROOT/'build/wolf_charge_crash'
backup=Path((ROOT/'build/current_charge_crash_backup.txt').read_text(encoding='utf-8').strip())
OLD=backup/'WeaponModelReplacement/Custom/khravengger'
current=json.loads((ASSET/'build.json').read_text())
legacy=json.loads((OLD/'build.json').read_text())
spec=importlib.util.spec_from_file_location('hash64','<CHARACTER_WORKSPACE>/tools/bitsquid-addon/murmur/murmurhash64.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
bad={r['key']['name'] for r in current['resources'] if r['key']['type']=='material' and blocked_material(r['key']['name'])}
assert len(bad)==3,bad
bad_ids={'#'+f'{h.hash64(name):016x}' for name in bad}
resources={(r['key']['type'],r['key']['name']):r for r in current['resources']}
particles=[r for r in current['resources'] if r['key']['type']=='particles']
assert len(particles)==30
def reachable(key,seen=None):
    seen=seen if seen is not None else set()
    if (key['type'],key['name']) in seen:return set()
    seen.add((key['type'],key['name']))
    result={key['name']} if key['type']=='material' else set()
    entry=resources.get((key['type'],key['name']))
    if entry:
        for dep in entry['dependencies']:result|=reachable(dep,seen)
    return result
for entry in particles:
    assert not reachable(entry['key'])&bad,entry['key']
affected=[r for r in legacy['resources'] if r['key']['type']=='particles' and any(d['name'] in bad for d in r['dependencies'])]
assert len(affected)==6
compiler=ROOT/'tools/compiler/DarktideGLBCompiler.exe'
def readback(asset,entry,suffix):
    name=entry['key']['name'].rsplit('/',1)[1]
    target=OUT/(name+'_'+suffix+'.json')
    subprocess.run([str(compiler),'--particles',str(asset/entry['file']['path']),str(target)],check=True,capture_output=True)
    return json.loads(target.read_text())
def origin_id(entry):
    match=re.search(r'/fx_(?:unit_)?([0-9a-f]{16})_',entry['key']['name'])
    return (entry['key']['type'],match.group(1)) if match else (entry['key']['type'],entry['key']['name'])
origins={'#'+f'{h.hash64(r["key"]["name"]):016x}':origin_id(r)
         for source in (current,legacy) for r in source['resources']}
def normalize(value):
    if isinstance(value,str):return origins.get(value.lower(),value)
    if isinstance(value,list):return [normalize(x) for x in value]
    if isinstance(value,dict):return {k:normalize(v) for k,v in value.items()}
    return value
removed_total=0;verified=[]
for old in affected:
    entry=resources[(old['key']['type'],old['key']['name'])]
    before=readback(OLD,old,'legacy');actual=readback(ASSET,entry,'fixed')
    expected=copy.deepcopy(before);removed=0
    for system in expected['systems']:
        retained=[]
        for draw in system['visualizers']:
            if draw.get('material','').lower() in bad_ids:removed+=1
            else:retained.append(draw)
        system['visualizers']=retained
    assert removed>0,old['key']
    assert normalize(expected)==normalize(actual),('Unexpected native particle field change',old['key'])
    assert sum(len(s['visualizers']) for s in actual['systems'])>0,old['key']
    removed_total+=removed;verified.append(old['key']['name'])
assert removed_total==24,removed_total
source_removed=0
for palette in ('ice','violet'):
    original=json.loads((OUT/(palette+'_original_effects.gltf')).read_text())
    for node in original['nodes']:
        effect=node['extras']['darktide_asset']['particles']['effect']
        source_removed+=len(sanitize(effect));assert not sanitize(effect)
assert source_removed==24
intentional_edge_changes={'khravengger.unit','langzhifei.unit','ice_charge_aura.particles',
    'violet_charge_aura.particles','ice_forcesword_2h_stage2.particles','ice_forcesword_2h_stage2_loop.particles'}
for path in OLD.rglob('*'):
    if path.is_file() and path.name!='build.json' and path.name not in {n.rsplit('/',1)[1]+'.particles' for n in verified}:
        if path.name not in intentional_edge_changes:
            assert path.read_bytes()==(ASSET/path.relative_to(OLD)).read_bytes(),path
report={'blocked_shader':BAD_SHADER,'legacy_unsafe_effects_reproduced':len(affected),
    'native_particle_effects_verified':len(verified),'particle_roots_without_blocked_materials':len(particles),
    'removed_render_passes':removed_total,'all_other_native_particle_fields_equivalent_except_compiler_material_ids':True,
    'systems_variables_lifetimes_emitters_and_compatible_visualizers_preserved':True,
    'materials_textures_and_unrelated_particles_byte_unchanged':True,
    'intentional_blade_edge_changes':sorted(intentional_edge_changes),
    'sanitizer_idempotent':True,'in_game_crash_retest_completed':False}
(OUT/'render_safety_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('CHARGE_RENDER_SAFETY_OK',json.dumps(report))
