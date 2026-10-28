from pathlib import Path
import json,sys,subprocess,numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/blade_edge'
MOD=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'WeaponModelReplacement'
ASSET=MOD/'Custom/khravengger';report={}
for palette,model,count in [('ice','khravengger',46),('violet','langzhifei',19)]:
    p=ASSET/(palette+'_charge_aura.particles');target=OUT/(palette+'_aura_native.json')
    subprocess.run([str(ROOT/'tools/compiler/DarktideGLBCompiler.exe'),'--particles',str(p),str(target)],capture_output=True,check=True)
    actual=json.loads(target.read_text());edge=json.loads((OUT/(model+'_edge.json')).read_text());envelope=np.array(edge['envelope'])
    assert len(actual['systems'])==count and len({s['name'] for s in actual['systems']})==count
    max_distance=0
    for s in actual['systems']:
        assert len(s['visualizers'])==1 and s['visualizers'][0]['type']=='billboard'
        assert s['capacity']==3 and s['max_radius']<=.025001
        box=next(i for i in s['initializers'] if i['type']=='position_box');lo=np.array(box['min']);hi=np.array(box['max']);mid=(lo+hi)*.5
        assert lo[2]>edge['start_z'] and hi[2]<envelope[-1,0]
        right=np.interp(mid[2],envelope[:,0],envelope[:,2]);d=abs(mid[1]-right)
        if len(edge['sides'])==2:d=min(d,abs(mid[1]-np.interp(mid[2],envelope[:,0],envelope[:,1])))
        assert d<.0016 and np.max(hi[:2]-lo[:2])<.00201
        max_distance=max(max_distance,float(d))
        size=next(i for i in s['initializers'] if i['type']=='random_float' and i['channel']=='c28')
        assert .0089<=size['min']<=size['max']<=.01301
        assert not any(i['type']=='burst_emitter' for i in s['simulators'])
    report[palette]={'emitters':count,'light_draws':0,'max_emitter_distance_from_edge_m':max_distance,'max_flash_size_m':.013}
for name in ('ice_forcesword_2h_stage2','ice_forcesword_2h_stage2_loop'):
    target=OUT/(name+'_native.json')
    subprocess.run([str(ROOT/'tools/compiler/DarktideGLBCompiler.exe'),'--particles',str(ASSET/(name+'.particles')),str(target)],capture_output=True,check=True)
    desc=json.loads(target.read_text());assert desc['systems'] and all(not s['visualizers'] for s in desc['systems'])
r=subprocess.run(['<LUA_EXE>',str(ROOT/'tools/test_blade_charge.lua'),str(MOD.parent)],capture_output=True,text=True,check=True)
assert 'BLADE_CHARGE_TESTS_OK 8' in r.stdout
report.update({'runtime_edge_size_checks':8,'broad_native_stage_draws_replaced':True,'in_game_visual_verified':False})
(OUT/'charge_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('BLADE_CHARGE_VERIFIED',json.dumps(report))
