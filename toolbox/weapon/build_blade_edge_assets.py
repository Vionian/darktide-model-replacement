"""Compile only owned units / blade-charge particles and merge their closures."""
from pathlib import Path
import copy,hashlib,importlib.util,json,os,shutil,subprocess
from particle_render_safety import sanitize
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/blade_edge'
ASSET=ROOT/'WeaponModelReplacement/Custom/khravengger'
GAME=Path('<DARKTIDE_GAME>')
COMPILER=ROOT/'tools/compiler/DarktideGLBCompiler.exe'
spec=importlib.util.spec_from_file_location('h','<CHARACTER_WORKSPACE>/tools/bitsquid-addon/murmur/murmurhash64.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
manifest=json.loads((ASSET/'build.json').read_text());before={p.relative_to(ASSET).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in ASSET.rglob('*') if p.is_file()}
def run(args,log,env=None):
    r=subprocess.run([str(COMPILER)]+list(map(str,args)),capture_output=True,text=True,encoding='utf-8',errors='replace',env=env)
    (OUT/log).write_text(r.stdout+r.stderr,encoding='utf-8')
    assert r.returncode==0,(log,r.stdout[-2000:],r.stderr[-2000:])
def merge(folder,carrier=None):
    incoming=json.loads((folder/'build.json').read_text())
    for r in incoming['resources']:
        key=r['key']
        if key['type']=='unit' and key['name']==carrier:continue
        previous=next((p for p in manifest['resources'] if p['key']==key),None)
        owned=key['type'] in ('unit','particles')
        if previous and not owned:
            for info in [r['file']]+([r['stream']['file']] if r.get('stream') else []):
                assert (ASSET/info['path']).read_bytes()==(folder/info['path']).read_bytes(),key
            continue
        if previous:manifest['resources'].remove(previous)
        manifest['resources'].append(r)
        for info in [r['file']]+([r['stream']['file']] if r.get('stream') else []):
            dest=ASSET/info['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(folder/info['path'],dest)
        if owned and key not in manifest['roots']:manifest['roots'].append(key)
for name in ('khravengger','langzhifei'):
    folder=OUT/(name+'_compiled')
    run([ROOT/'build/revision'/(name+'.glb'),'-o',folder,'--asset-path','content/mods/weapon_model_replacement/'+name,'--no-physics'],name+'_compile.log')
    merge(folder)
audit={'effects':{},'shader_safety_preserved':True}
for palette,folder,gltf,model in [('ice','ice_fx','ice_effects.gltf','khravengger'),('violet','wolf_violet','violet_effects.gltf','langzhifei')]:
    work=ROOT/'build'/folder;source=work/gltf;graph=json.loads(source.read_text());selected=[]
    edge=json.loads((OUT/(model+'_edge.json')).read_text());envp=edge['envelope']
    import numpy as np
    envp=np.asarray(envp);zs=np.linspace(edge['start_z']+.009,float(envp[-1,0])-.012,23 if palette=='ice' else 19)
    for node in graph['nodes']:
        e=node['extras']['darktide_asset']['particles']['effect'];name=node['name']
        if name.endswith('charge_aura'):
            # Reuse a proven compatible flash billboard. Broad lights and
            # smoke are removed; the persistent signal is the blade ribbon.
            template=copy.deepcopy(e['systems'][3]);systems=[]
            for side in edge['sides']:
                for i,z in enumerate(zs):
                    y=float(np.interp(z,envp[:,0],envp[:,2 if side==1 else 1]))-side*.0015
                    s=copy.deepcopy(template);s['name']='#'+f'{h.hash64(palette+str(side)+str(i))>>32:08x}'
                    s['capacity']=3;s['max_radius']=.025
                    for init in s['initializers']:
                        if init['type']=='position_box':init['min']=[-.001,y-.001,float(z)-.003];init['max']=[.001,y+.001,float(z)+.003]
                        if init['type']=='random_float' and init.get('channel')=='c28':init['min']=.009;init['max']=.013
                    s['simulators']=[x for x in s['simulators'] if x['type']!='burst_emitter']
                    for sim in s['simulators']:
                        if sim['type']=='rate_emitter':sim['rate_min']=8;sim['rate_max']=8
                    systems.append(s)
            e['systems']=systems
        elif name in ('ice_forcesword_2h_stage2','ice_forcesword_2h_stage2_loop'):
            # Native stage callbacks retain ownership and timing; the single
            # mod-owned aura and serialized edge ribbons replace broad draws.
            for system in e['systems']:system['visualizers']=[]
        else:continue
        sanitize(e);selected.append(node)
        audit['effects'][name]={'systems':len(e['systems']),'draws':sum(len(s['visualizers']) for s in e['systems']),
                                'light_draws':sum(v['type']=='light' for s in e['systems'] for v in s['visualizers'])}
    candidate={'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':list(range(len(selected)))}],'nodes':selected}
    path=OUT/(palette+'_edge_effects.gltf');path.write_text(json.dumps(candidate),encoding='utf-8')
    env=os.environ.copy();env['DARKTIDE_GAME_ROOT']=str(work/'game');env['DARKTIDE_OODLE_DLL']=str(GAME/'binaries/oo2core_9_win64.dll')
    compiled=OUT/(palette+'_fx_compiled');carrier='content/mods/weapon_model_replacement/'+palette
    run([path,'-o',compiled,'--asset-path',carrier,'--no-physics','--no-materials'],palette+'_fx_compile.log',env)
    merge(compiled,carrier);source.write_text(json.dumps(graph),encoding='utf-8')
manifest['artifacts']=[]
for r in manifest['resources']:
    for role,info in [('primary',r['file'])]+([('stream',r['stream']['file'])] if r.get('stream') else []):
        manifest['artifacts'].append({'resource':r['key'],'role':role,'path':info['path'],'size':info['size']})
(ASSET/'build.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
changed={p for p,digest in before.items() if hashlib.sha256((ASSET/p).read_bytes()).hexdigest()!=digest}
allowed={'build.json','khravengger.unit','langzhifei.unit'}|{n+'.particles' for n in audit['effects']}
assert changed<=allowed,(changed,allowed)
assert len(manifest['resources'])==278 and len(manifest['artifacts'])==481
audit.update({'changed_asset_files':sorted(changed),'resources':len(manifest['resources']),'artifacts':len(manifest['artifacts']),
              'original_materials_textures_and_unrelated_particles_byte_unchanged':True,'in_game_visual_verified':False})
(OUT/'asset_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print('BLADE_EDGE_ASSETS_BUILT',json.dumps(audit))
