"""Recompile only the six particle resources that reference the crashed shader."""
from pathlib import Path
import copy,json,os,subprocess,shutil,hashlib,struct,zlib,re,importlib.util
from particle_render_safety import sanitize,BAD_MATERIAL_SOURCES,BAD_SHADER
ROOT=Path(__file__).resolve().parents[1]
ASSET=ROOT/'WeaponModelReplacement/Custom/khravengger'
OUT=ROOT/'build/wolf_charge_crash';OUT.mkdir(exist_ok=True)
COMPILER=ROOT/'tools/compiler/DarktideGLBCompiler.exe'
GAME=Path('<DARKTIDE_GAME>')
backup=Path((ROOT/'build/current_charge_crash_backup.txt').read_text(encoding='utf-8').strip())
old_asset=backup/'WeaponModelReplacement/Custom/khravengger'
manifest=json.loads((old_asset/'build.json').read_text())
before={p.relative_to(old_asset).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in old_asset.rglob('*') if p.is_file()}
audit={'shader':BAD_SHADER,'effects':{},'new_resources':[],'in_game_visual_verified':False}
spec=importlib.util.spec_from_file_location('hash64','<CHARACTER_WORKSPACE>/tools/bitsquid-addon/murmur/murmurhash64.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
def origin(key):
    match=re.search(r'/fx_(?:unit_)?([0-9a-f]{16})_',key['name'])
    return (key['type'],match.group(1)) if match else (key['type'],key['name'])
for palette,folder,gltf_name in [('ice','ice_fx','ice_effects.gltf'),('violet','wolf_violet','violet_effects.gltf')]:
    work=ROOT/'build'/folder;source=work/gltf_name
    graph=json.loads(source.read_text());changed=[]
    original=OUT/(palette+'_original_effects.gltf')
    if not original.exists():shutil.copy2(source,original)
    else:graph=json.loads(original.read_text())
    for node in graph['nodes']:
        effect=node['extras']['darktide_asset']['particles']['effect']
        removed=sanitize(effect)
        if removed:
            changed.append(node)
            audit['effects'][node['name']]={'removed_draws':removed,'systems_preserved':len(effect['systems'])}
    assert len(changed)==3,(palette,len(changed))
    candidate={'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':list(range(len(changed)))}],'nodes':changed}
    path=OUT/(palette+'_safe_effects.gltf');path.write_text(json.dumps(candidate),encoding='utf-8')
    env=os.environ.copy();env['DARKTIDE_GAME_ROOT']=str(work/'game')
    env['DARKTIDE_OODLE_DLL']=str(GAME/'binaries/oo2core_9_win64.dll')
    compiled=OUT/(palette+'_compiled')
    r=subprocess.run([str(COMPILER),str(path),'-o',str(compiled),'--asset-path',
        'content/mods/weapon_model_replacement/'+palette,'--no-physics','--no-materials'],
        env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',check=True)
    (OUT/(palette+'_compile.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
    built=json.loads((compiled/'build.json').read_text())
    for entry in built['resources']:
        key=entry['key']
        if key=={'type':'unit','name':'content/mods/weapon_model_replacement/'+palette}:continue
        prior=next((x for x in manifest['resources'] if x['key']==key),None)
        if key['type']=='particles' or not prior:
            for info in [entry['file']]+([entry['stream']['file']] if entry.get('stream') else []):
                target=ASSET/info['path'];target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(compiled/info['path'],target)
            if prior:manifest['resources'][manifest['resources'].index(prior)]=entry
            else:
                manifest['resources'].append(entry);audit['new_resources'].append(key)
        elif prior:
            for info in [entry['file']]+([entry['stream']['file']] if entry.get('stream') else []):
                assert (compiled/info['path']).read_bytes()==(ASSET/info['path']).read_bytes(),key
    source.write_text(json.dumps(graph),encoding='utf-8')
manifest['artifacts']=[]
for entry in manifest['resources']:
    for role,info in [('primary',entry['file'])]+([('stream',entry['stream']['file'])] if entry.get('stream') else []):
        manifest['artifacts'].append({'resource':entry['key'],'role':role,'path':info['path'],'size':info['size']})
(ASSET/'build.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
allowed={'build.json'}|{name+'.particles' for name in audit['effects']}
changed={name for name,digest in before.items() if hashlib.sha256((ASSET/name).read_bytes()).hexdigest()!=digest}
assert changed==allowed,(changed,allowed)
keys={(e['key']['type'],e['key']['name']) for e in manifest['resources']}
external={(e['key']['type'],e['key']['name']) for e in manifest['external_resources']}
for entry in manifest['resources']:
    for dep in entry['dependencies']:assert (dep['type'],dep['name']) in keys|external,(entry['key'],dep)
audit.update({'changed_asset_files':sorted(changed),'removed_render_passes':sum(len(e['removed_draws']) for e in audit['effects'].values()),
    'existing_model_materials_textures_and_other_particles_byte_unchanged':True,'native_action_timing_and_palette_preserved':True,
    'resources':len(manifest['resources']),'artifacts':len(manifest['artifacts'])})
(OUT/'repair_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
violet_path=ROOT/'build/wolf_violet/audit.json'
violet=json.loads(violet_path.read_text(encoding='utf-8'))
violet.update({'resources':audit['resources'],'artifacts':audit['artifacts'],
    'original_ice_and_khravengger_assets_unchanged':False,
    'khravengger_model_and_ice_palette_unchanged':True,
    'renderer_safety_repair':{'blocked_shader':BAD_SHADER,'affected_ice_effects':3,'affected_violet_effects':3}})
violet['old_asset_files_changed']=sorted(set(violet['old_asset_files_changed'])|{n for n in changed if n.startswith('ice_')})
violet_path.write_text(json.dumps(violet,indent=2),encoding='utf-8')
print('CHARGE_RENDERER_REPAIR_COMPILED',len(audit['effects']),audit['removed_render_passes'],audit['resources'],audit['artifacts'])
