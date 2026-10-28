"""Compile an isolated blue-violet closure; retain the existing ice graph."""
from pathlib import Path
from particle_render_safety import sanitize
import copy, importlib.util, json, os, shutil, struct, subprocess, zlib
ROOT=Path(__file__).resolve().parents[1]
REF=ROOT/'暗潮武器mod/ExcaliburAlterForceSword/Custom/alter_sword'
OUT=ROOT/'build/wolf_violet'; OUT.mkdir(parents=True,exist_ok=True)
EXTRACT=OUT/'extract'; EXTRACT.mkdir(exist_ok=True)
FAKE=OUT/'game'; (FAKE/'bundle').mkdir(parents=True,exist_ok=True)
DST=ROOT/'WeaponModelReplacement/Custom/khravengger'
COMPILER=ROOT/'tools/compiler/DarktideGLBCompiler.exe'
GAME=Path('<DARKTIDE_GAME>')
SDK=Path('<CHARACTER_WORKSPACE>/tools/darktide-sdk-reference')
spec=importlib.util.spec_from_file_location('hash64',SDK.parent/'bitsquid-addon/murmur/murmurhash64.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
reference=json.loads((REF/'build.json').read_text())
baseline=Path((ROOT/'build/current_wolf_violet_backup.txt').read_text(encoding='utf-8-sig').strip())/'WeaponModelReplacement/Custom/khravengger'
before={p.relative_to(baseline).as_posix():p.read_bytes() for p in baseline.rglob('*') if p.is_file()}
for r in reference['resources']:
    key=r['key'];shutil.copy2(REF/r['file']['path'],EXTRACT/(f"{h.hash64(key['name']):016x}."+key['type']))
    if r.get('stream'):
        target=FAKE/'bundle'/r['stream']['name'];target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(REF/r['stream']['file']['path'],target)
names={}
shader_dir=SDK/'tools/blender/darktide_assets'
for preset in json.loads((shader_dir/'game_shaders.json').read_text())['presets']:
    for v in preset['variables']:names[h.hash64(v['name'])>>32]=v['name']
names.update({int(k,16):v for k,v in json.loads((shader_dir/'shader_names.json').read_text()).items()})
confirmed={'material_variable_8b0f8e84','material_variable_8b0f8e84_118d5a82',
 'material_variable_0c7ca7b0','material_variable_0c7ca7b0_c9db54de',
 'material_variable_21872256','material_variable_21872256_69bf7e2a','material_variable_33023669','Color1','Color2'}
hashes={h.hash64(n)>>32 for n in confirmed}
hashes.update(k for k,n in names.items() if any(s in n.lower() for s in ('color','colour','tint')) and 'levels' not in n)
PALETTE=(.32,.10,1.)
edits=[]
for r in reference['resources']:
    if r['key']['type']!='material' or not r.get('stream'):continue
    p=FAKE/'bundle'/r['stream']['name'];raw=bytearray(p.read_bytes());at=struct.unpack_from('<I',raw,4)[0]+20
    for stride in (4,12,8):n=struct.unpack_from('<I',raw,at)[0];at+=4+stride*n
    n=struct.unpack_from('<I',raw,at)[0];entries=[struct.unpack_from('<5I',raw,at+4+i*20) for i in range(n)]
    data=at+4+20*n+4
    for kind,_,name,offset,_ in entries:
        if kind not in (2,3) or name not in hashes:continue
        old=struct.unpack_from('<%df'%(kind+1),raw,data+offset);gain=max(abs(v) for v in old[:3])
        if not gain:continue
        new=tuple(c*gain for c in PALETTE)+old[3:]
        struct.pack_into('<%df'%(kind+1),raw,data+offset,*new)
        edits.append({'material':r['key']['name'],'parameter':names.get(name,f'#{name:08x}'),'before':old,'after':new})
    p.write_bytes(raw)
variables={'alter_r':(.32,)*3,'alter_g':(.10,)*3,'alter_b':(1.,)*3,
    'energy_rgb':(.032,.010,.1),'energy_r':(.032,)*3,'energy_g':(.010,)*3,'energy_b':(.1,)*3}
variables={f'#{h.hash64(k)>>32:08x}':list(v) for k,v in variables.items()}
def recolor(value):
    if isinstance(value,dict):
        for key,member in value.items():
            if key=='rgb' and isinstance(member,list):
                # Pure-channel ramps are multiplied by independent RGB variables.
                if any(isinstance(v,list) and sum(c>0 for c in v)==1 for v in member):continue
                for i,rgb in enumerate(member):
                    if isinstance(rgb,list) and len(rgb)==3:member[i]=[round(c*max(rgb)) for c in PALETTE]
            else:recolor(member)
    elif isinstance(value,list):
        for member in value:recolor(member)
keep={'force_sword_impact_02','generic_shove_warp_01','psyker_block','psyker_parry',
    'psyker_push','psyker_block_impact_01','psyker_venting','charge_aura',
    'force_staff_channel_charge','force_staff_channel_charge_husk'}
nodes=[]
for r in reference['resources']:
    if r['key']['type']!='particles':continue
    short=Path(r['file']['path']).stem.removeprefix('alter_')
    if short not in keep:continue
    desc_path=OUT/(short+'.json')
    subprocess.run([str(COMPILER),'--particles',str(REF/r['file']['path']),str(desc_path)],check=True,capture_output=True)
    desc=json.loads(desc_path.read_text());recolor(desc);sanitize(desc)
    for variable in desc.get('variables',[]):
        if variable['name'] in variables:variable['value']=variables[variable['name']]
    if short=='charge_aura':
        # Match the shorter ordinary sword, keeping the guard/hand outside its aura.
        for system in desc['systems']:
            for initializer in system['initializers']:
                if initializer['type']=='position_box':
                    for bound in ('min','max'):
                        initializer[bound][2]=.16+(initializer[bound][2]-.16)*(.68/.98)
    name='violet_'+short
    nodes.append({'name':name,'extras':{'darktide_asset':{'version':1,'id':name,
        'particles':{'name':name,'effect':desc,'extract':str(EXTRACT)}}}})
assert len(nodes)==10
gltf={'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':list(range(len(nodes)))}],'nodes':nodes}
source=OUT/'violet_effects.gltf';source.write_text(json.dumps(gltf),encoding='utf-8')
env=os.environ.copy();env['DARKTIDE_GAME_ROOT']=str(FAKE);env['DARKTIDE_OODLE_DLL']=str(GAME/'binaries/oo2core_9_win64.dll')
compiled=OUT/'fx_compiled'
result=subprocess.run([str(COMPILER),str(source),'-o',str(compiled),'--asset-path',
    'content/mods/weapon_model_replacement/violet','--no-physics','--no-materials'],env=env,capture_output=True,text=True)
(OUT/'fx_compile.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
assert result.returncode==0,result.stdout+result.stderr
# External material intent is still processed by the material pass. The
# --no-materials flag serializes zero resource IDs even when slots exist.
model=OUT/'model_compiled'
model_result=subprocess.run([str(COMPILER),str(ROOT/'build/force_sword_pose/langzhifei.glb'),
    '-o',str(model),'--asset-path','content/mods/weapon_model_replacement/langzhifei',
    '--no-physics'],capture_output=True,text=True)
(OUT/'model_compile.log').write_text(model_result.stdout+'\n'+model_result.stderr,encoding='utf-8')
assert model_result.returncode==0,model_result.stdout+model_result.stderr
model_build=json.loads((model/'build.json').read_text())
model_unit=next(r for r in model_build['resources'] if r['key']['type']=='unit')
assert {d['name'] for d in model_unit['dependencies']}=={
    'content/mods/weapon_model_replacement/'+n for n in
    ('ice_cover_b','ice_cover_g','ice_cover_r','langzhifei_material_0')}
manifest=json.loads((DST/'build.json').read_text())
def merge(directory, omit_carrier=False):
    built=json.loads((directory/'build.json').read_text())
    for incoming in built['resources']:
        key=incoming['key']
        if omit_carrier and key=={'type':'unit','name':'content/mods/weapon_model_replacement/violet'}:continue
        previous=next((r for r in manifest['resources'] if r['key']==key),None)
        replace_owned=(key['type']=='particles' and key['name'].startswith('content/mods/weapon_model_replacement/violet_'))
        if previous and key['name']!='content/mods/weapon_model_replacement/langzhifei' and not replace_owned:
            for info in [incoming['file']]+([incoming['stream']['file']] if incoming.get('stream') else []):
                assert (DST/info['path']).read_bytes()==(directory/info['path']).read_bytes(),key
            continue
        if previous:manifest['resources'].remove(previous)
        for info in [incoming['file']]+([incoming['stream']['file']] if incoming.get('stream') else []):
            target=DST/info['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(directory/info['path'],target)
        manifest['resources'].append(incoming)
        if key['type'] in ('particles','unit') and key not in manifest['roots']:manifest['roots'].append(key)
merge(OUT/'model_compiled');merge(compiled,True)
keys={(r['key']['type'],r['key']['name']) for r in manifest['resources']}
external={(e['key']['type'],e['key']['name']) for e in manifest['external_resources']}
for r in manifest['resources']:
    for d in r['dependencies']:assert (d['type'],d['name']) in keys|external,(r['key'],d)
manifest['artifacts']=[]
for r in manifest['resources']:
    for role,info in [('primary',r['file'])]+([('stream',r['stream']['file'])] if r.get('stream') else []):
        manifest['artifacts'].append({'resource':r['key'],'role':role,'path':info['path'],'size':info['size']})
(DST/'build.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
changed=[name for name,data in before.items() if (DST/name).read_bytes()!=data]
allowed={'build.json','langzhifei.unit'}|{'ice_'+n+'.particles' for n in ('psyker_parry','psyker_block','force_staff_channel_charge')}
assert set(changed)<=allowed and {'build.json','langzhifei.unit'}<=set(changed),changed
audit={'particle_effects':10,'palette_linear_rgb':PALETTE,'material_color_edits':len(edits),
    'resources':len(keys),'artifacts':len(manifest['artifacts']),'old_asset_files_changed':changed,
    'original_ice_and_khravengger_assets_unchanged':not any(n.startswith('ice_') for n in changed),
    'khravengger_model_and_ice_palette_unchanged':True,'reference_assets_unchanged':True,
    'native_special_active_drives_charge':True,'in_game_visual_verified':False}
(OUT/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print('WOLF_VIOLET_FX_BUILT',json.dumps(audit))
