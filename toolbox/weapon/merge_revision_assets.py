from pathlib import Path
import json,struct,hashlib,importlib.util,copy,zlib,shutil
ROOT=Path(__file__).resolve().parents[1];DST=ROOT/'WeaponModelReplacement/Custom/khravengger'
REF=ROOT/'暗潮武器mod/ExcaliburAlterForceSword/Custom/alter_sword'
spec=importlib.util.spec_from_file_location('h','<CHARACTER_WORKSPACE>/tools/bitsquid-addon/murmur/murmurhash64.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
manifest=json.loads((DST/'build.json').read_text());reference=json.loads((REF/'build.json').read_text())
resources={(r['key']['type'],r['key']['name']):r for r in reference['resources']}
def meta(path,data):
    p=DST/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    return {'path':path,'size':len(data),'crc32':f'{zlib.crc32(data):08x}'}
def add(r,source=None):
    key=r['key'];old=next((x for x in manifest['resources'] if x['key']==key),None)
    if old and source and key['type']=='unit' and key['name'] in (
        'content/mods/weapon_model_replacement/khravengger',
        'content/mods/weapon_model_replacement/langzhifei'):
        manifest['resources'].remove(old);old=None
    if old:
        if source:
            for f in [r['file']]+([r['stream']['file']] if r.get('stream') else []):
                assert (DST/f['path']).read_bytes()==(source/f['path']).read_bytes(),f
        return
    if source:
        for f in [r['file']]+([r['stream']['file']] if r.get('stream') else []):
            p=DST/f['path'];p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/f['path'],p)
    manifest['resources'].append(r)
def resolve(d):
    if (d['type'],d['name']) in resources:return d
    if d['name'].startswith('#ID['):
        token=d['name'][4:-1]
        choices=[r['key'] for r in reference['resources'] if r['key']['type']==d['type'] and ('fx_tex_'+token+'_') in r['key']['name']]
        if not choices:
            external={'key':d,'package_member':True}
            if external not in manifest['external_resources']:manifest['external_resources'].append(external)
            return d
        return choices[0]
    raise ValueError(d)
def own_reference(key):
    if key['name'].startswith('#ID['):return
    r=copy.deepcopy(resources[(key['type'],key['name'])])
    for d in r['dependencies']:
        if d['name'].startswith('#ID['):
            external={'key':d,'package_member':True}
            if external not in manifest['external_resources']:manifest['external_resources'].append(external)
        else:own_reference(d)
    add(r,REF)
for index,ch in ((1,'b'),(2,'g'),(3,'r')):
    r=copy.deepcopy(next(x for x in reference['resources'] if x['key']['name'].endswith('alter_sword_material_'+str(index))))
    raw=bytearray((REF/r['stream']['file']['path']).read_bytes());off=struct.unpack_from('<I',raw,4)[0]
    # MaterialTemplate: u32 shader name, provider u64, parent u64, then arrays.
    at=off+20;n=struct.unpack_from('<I',raw,at)[0];at+=4+4*n
    n=struct.unpack_from('<I',raw,at)[0];at+=4
    deps=[]
    for d in r['dependencies']:
        fixed=resolve(d);own_reference(fixed);deps.append(fixed)
        if fixed!=d:
            old=int(d['name'][4:-1],16);new=h.hash64(fixed['name'])
            for j in range(n):
                pos=at+j*12+4
                if struct.unpack_from('<Q',raw,pos)[0]==old:struct.pack_into('<Q',raw,pos,new)
    key={'type':'material','name':'content/mods/weapon_model_replacement/ice_cover_'+ch}
    stream_name='data/am/'+hashlib.sha256(raw).hexdigest()[:16]
    wrapper=bytearray((REF/r['file']['path']).read_bytes());struct.pack_into('<Q',wrapper,8,h.hash64(key['name']))
    old_name=r['stream']['name'].encode();assert len(old_name)==len(stream_name);wrapper=wrapper.replace(old_name,stream_name.encode())
    r={'key':key,'name_hash':f"{h.hash64(key['name']):016x}",'file':meta('ice_cover_'+ch+'.material',wrapper),'stream':{'name':stream_name,'file':meta(stream_name,raw)},'dependencies':deps}
    add(r)
for folder in ('khravengger_compiled','wolf_compiled'):
    source=ROOT/'build/revision'/folder;built=json.loads((source/'build.json').read_text())
    for r in built['resources']:add(r,source)
    for key in built['roots']:
        if key not in manifest['roots']:manifest['roots'].append(key)
# Merge across resource graphs, then require closure with no opaque dependencies.
keys={(r['key']['type'],r['key']['name']) for r in manifest['resources']}
for r in manifest['resources']:
    for d in r['dependencies']:assert (d['type'],d['name']) in keys or any(e['key']==d for e in manifest['external_resources']),(r['key'],d)
manifest['artifacts']=[]
for r in manifest['resources']:
    for role,f in [('primary',r['file'])]+([('stream',r['stream']['file'])] if r.get('stream') else []):
        manifest['artifacts'].append({'resource':r['key'],'role':role,'path':f['path'],'size':f['size']})
(DST/'build.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('MERGED_CLOSED_RESOURCES',len(keys),'ARTIFACTS',len(manifest['artifacts']))
