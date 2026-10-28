"""Compile isolated ice variants of the supplied sword's particle effects.
The original reference and installed game resources are never edited."""
from pathlib import Path
from particle_render_safety import sanitize
import copy, hashlib, importlib.util, json, os, shutil, struct, subprocess, zlib
ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT/'WeaponModelReplacement'
REF = ROOT/'暗潮武器mod/ExcaliburAlterForceSword/Custom/alter_sword'
WORK = ROOT/'build/ice_fx'
COMPILER = ROOT/'tools/compiler/DarktideGLBCompiler.exe'
GAME = Path('<DARKTIDE_GAME>')
SDK = Path('<CHARACTER_WORKSPACE>/tools/darktide-sdk-reference')
spec = importlib.util.spec_from_file_location('hash64', SDK.parent/'bitsquid-addon/murmur/murmurhash64.py')
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
WORK.mkdir(parents=True, exist_ok=True)
extract = WORK/'extract'; extract.mkdir(exist_ok=True)
fake = WORK/'game'; (fake/'bundle').mkdir(parents=True, exist_ok=True)
reference = json.loads((REF/'build.json').read_text())
for r in reference['resources']:
    key = r['key']; dst = extract/(f"{h.hash64(key['name']):016x}."+key['type'])
    shutil.copy2(REF/r['file']['path'], dst)
    if r.get('stream'):
        stream = fake/'bundle'/r['stream']['name']; stream.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(REF/r['stream']['file']['path'], stream)
names = {}
shader_dir = SDK/'tools/blender/darktide_assets'
for preset in json.loads((shader_dir/'game_shaders.json').read_text())['presets']:
    for v in preset['variables']: names[h.hash64(v['name']) >> 32] = v['name']
names.update({int(k,16):v for k,v in json.loads((shader_dir/'shader_names.json').read_text()).items()})
confirmed = {'material_variable_8b0f8e84','material_variable_8b0f8e84_118d5a82',
 'material_variable_0c7ca7b0','material_variable_0c7ca7b0_c9db54de',
 'material_variable_21872256','material_variable_21872256_69bf7e2a',
 'material_variable_33023669','Color1','Color2'}
color_hashes = {h.hash64(n)>>32 for n in confirmed}
color_hashes.update(k for k,n in names.items() if any(t in n.lower() for t in ('color','colour','tint')) and 'levels' not in n)
ICE = (.16,.67,1.)
material_edits = []
for r in reference['resources']:
    if r['key']['type'] != 'material' or not r.get('stream'): continue
    stream = fake/'bundle'/r['stream']['name']; raw = bytearray(stream.read_bytes())
    offset = struct.unpack_from('<I',raw,4)[0]+20
    for size in (4,12,8):
        n=struct.unpack_from('<I',raw,offset)[0];offset+=4+size*n
    n=struct.unpack_from('<I',raw,offset)[0]
    entries=[struct.unpack_from('<5I',raw,offset+4+i*20) for i in range(n)]
    data_offset=offset+4+20*n+4
    for kind,_,name,at,_ in entries:
        if kind not in (2,3) or name not in color_hashes: continue
        values=struct.unpack_from('<%df'%(kind+1),raw,data_offset+at)
        gain=max(abs(v) for v in values[:3])
        if gain == 0: continue
        new=tuple(c*gain for c in ICE)+values[3:]
        struct.pack_into('<%df'%(kind+1),raw,data_offset+at,*new)
        material_edits.append({'resource':r['key']['name'],'parameter':names.get(name,f'#{name:08x}'),'before':values,'after':new})
    stream.write_bytes(raw)
variables = {'alter_r':(.16,)*3,'alter_g':(.67,)*3,'alter_b':(1.,)*3,
 'energy_rgb':(.016,.067,.1),'energy_r':(.016,)*3,'energy_g':(.067,)*3,'energy_b':(.1,)*3}
variables = {f'#{h.hash64(k)>>32:08x}':list(v) for k,v in variables.items()}
gradient_count=0
def recolor(value):
    global gradient_count
    if isinstance(value,dict):
        for key,member in value.items():
            if key=='rgb' and isinstance(member,list):
                # Pure RGB ramps implement separate runtime channels; retain them.
                if any(isinstance(v,list) and sum(c>0 for c in v)==1 for v in member): continue
                for i,rgb in enumerate(member):
                    if isinstance(rgb,list) and len(rgb)==3:
                        gain=max(rgb);member[i]=[round(c*gain) for c in ICE];gradient_count+=1
            else: recolor(member)
    elif isinstance(value,list):
        for member in value: recolor(member)
nodes=[]; descriptions={}
for resource in reference['resources']:
    if resource['key']['type']!='particles':continue
    old=Path(resource['file']['path']).stem; name='ice_'+old.removeprefix('alter_')
    out=WORK/(old+'.json')
    subprocess.run([str(COMPILER),'--particles',str(REF/resource['file']['path']),str(out)],check=True,capture_output=True)
    desc=json.loads(out.read_text());recolor(desc);sanitize(desc)
    for v in desc.get('variables',[]):
        if v['name'] in variables:v['value']=variables[v['name']]
    # Idle halo's reference color was baked red; its private material is recolored above.
    nodes.append({'name':name,'extras':{'darktide_asset':{'version':1,'id':name,
       'particles':{'name':name,'effect':desc,'extract':str(extract)}}}})
    descriptions[name]=desc
# One empty carrier is valid; each particles resource becomes an independent root.
gltf={'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':list(range(len(nodes)))}],'nodes':nodes}
input_path=WORK/'ice_effects.gltf';input_path.write_text(json.dumps(gltf),encoding='utf-8')
env=os.environ.copy();env['DARKTIDE_GAME_ROOT']=str(fake);env['DARKTIDE_OODLE_DLL']=str(GAME/'binaries/oo2core_9_win64.dll')
output=WORK/'compiled'
result=subprocess.run([str(COMPILER),str(input_path),'-o',str(output),'--asset-path','content/mods/weapon_model_replacement/ice','--no-physics','--no-materials'],env=env,capture_output=True,text=True)
(WORK/'compile.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
if result.returncode:raise RuntimeError(result.stdout+result.stderr)
built=json.loads((output/'build.json').read_text())
resources=[r for r in built['resources'] if r['key']!={'type':'unit','name':'content/mods/weapon_model_replacement/ice'}]
keys={(r['key']['type'],r['key']['name']) for r in resources}
for r in resources:
    for d in r['dependencies']:assert (d['type'],d['name']) in keys,(r['key'],d)
dst=MOD/'Custom/khravengger'
base=json.loads((dst/'build.json').read_text())
assert len(base['resources'])==8,'Start from the model-only build, not a previous FX build'
for r in resources:
    for info in [r['file']]+([r['stream']['file']] if r.get('stream') else []):
        src=output/info['path'];target=dst/info['path'];target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert target.read_bytes()==src.read_bytes(),target
        else:shutil.copy2(src,target)
base['resources']+=resources
base['roots'] += [r['key'] for r in resources if r['key']['type']=='particles']
base['artifacts'] += [a for a in built['artifacts'] if (a['resource']['type'],a['resource']['name']) in keys]
(dst/'build.json').write_text(json.dumps(base,indent=2),encoding='utf-8')
audit={'effects':len(descriptions),'material_color_edits':material_edits,'gradient_points':gradient_count,
 'resources_added':len(resources),'ice_linear_rgb':ICE,'reference_unchanged':True}
(WORK/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in audit.items() if k!='material_color_edits'}));print('MATERIAL_COLOR_EDITS',len(material_edits))
