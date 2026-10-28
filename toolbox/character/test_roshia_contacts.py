"""Offline execution of production Lua, with intentionally stale Unit world caches.

Export resulting node matrices for the actual compiled-mesh preview. Synthetic
driver poses are stress cases, not captured game weapon animations.
"""
import argparse,json,pathlib,sys,math
import numpy as np
from scipy.spatial.transform import Rotation as R
ROOT=pathlib.Path(__file__).resolve().parents[2]
options=argparse.ArgumentParser()
options.add_argument('output',type=pathlib.Path,nargs='?',default=ROOT/'tools/model-work/roshia/contact_tail_candidate')
options.add_argument('--cases',nargs='+')
opts=options.parse_args()
OUT=opts.output.resolve()
sys.path.insert(0,str(ROOT/'tools/model-work/python-deps'))
from lupa import LuaRuntime
fixture=json.loads((OUT/'runtime_fixture.json').read_text())
config=json.loads((OUT/'Custom/roshia_proportion_bones.json').read_text())
lua=LuaRuntime(unpack_returned_tuples=True)
lua.execute('''
math.atan2=math.atan
local mt={}
mt.__add=function(a,b)return Vector3(a.x+b.x,a.y+b.y,a.z+b.z)end
mt.__sub=function(a,b)return Vector3(a.x-b.x,a.y-b.y,a.z-b.z)end
mt.__mul=function(a,b)return Vector3(a.x*b,a.y*b,a.z*b)end
mt.__div=function(a,b)return Vector3(a.x/b,a.y/b,a.z/b)end
Vector3=setmetatable({}, {__call=function(_,x,y,z)return setmetatable({x=x,y=y,z=z},mt)end})
Quaternion={}
Vector3Box=function(v) local x,y,z=v.x,v.y,v.z;return {unbox=function()return Vector3(x,y,z)end}end
QuaternionBox=function(v) local x,y,z,w=v.x,v.y,v.z,v.w;return {unbox=function()return Quaternion.from_elements(x,y,z,w)end}end
''')
def vec(a):return lua.globals().Vector3(*map(float,a))
def arr(a):return np.array([a.x,a.y,a.z])
def quat(a):return lua.table_from(dict(zip(('x','y','z','w'),map(float,a))))
def qa(a):return np.array([a.x,a.y,a.z,a.w])
V=lua.globals().Vector3;Q=lua.globals().Quaternion
V.length=lambda v:float(np.linalg.norm(arr(v)))
V.dot=lambda a,b:float(arr(a)@arr(b))
V.cross=lambda a,b:vec(np.cross(arr(a),arr(b)))
Q.from_elements=lambda x,y,z,w:quat([x,y,z,w])
Q.to_elements=lambda q:tuple(qa(q))
Q.identity=lambda:quat([0,0,0,1])
Q.inverse=lambda q:quat(R.from_quat(qa(q)).inv().as_quat())
Q.multiply=lambda a,b:quat((R.from_quat(qa(a))*R.from_quat(qa(b))).as_quat())
Q.rotate=lambda q,v:vec(R.from_quat(qa(q)).apply(arr(v)))
Q.axis_angle=lambda v,a:quat(R.from_rotvec(arr(v)*a).as_quat())
names=fixture['names'];pars=fixture['parents']
native=np.array(fixture['template_world']).reshape(-1,4,4).transpose(0,2,1)
def fk(locals_,parents):
    cache={}
    def solve(i):
        if i not in cache:cache[i]=locals_[i] if parents[i]<0 else solve(parents[i])@locals_[i]
        return cache[i]
    return np.array([solve(i)for i in range(len(locals_))])
def localize(worlds,parents):return [np.linalg.inv(worlds[p])@w if p>=0 else w.copy()for p,w in zip(parents,worlds)]
def turn(a,b):
    a=a/np.linalg.norm(a);b=b/np.linalg.norm(b);v=np.cross(a,b);l=np.linalg.norm(v)
    return R.from_rotvec(v/l*np.arccos(np.clip(a@b,-1,1))).as_matrix() if l>1e-8 else np.eye(3)
def set_arm_direction(dl,side,upper_direction,elbow_delta=0,wrist_delta=0):
    ai,ei,wi=[names['j_'+side+k] for k in ('arm','forearm','hand')]
    worlds=fk(dl,pars)
    rot=turn(worlds[ei,:3,3]-worlds[ai,:3,3],np.array(upper_direction))@worlds[ai,:3,:3]
    dl[ai][:3,:3]=worlds[pars[ai],:3,:3].T@rot
    # The shared native rigs hinge at the elbow's local Z. Turning the
    # forearm independently toward a world vector introduced elbow yaw/roll
    # that no human elbow can perform; it was a bad animation fixture.
    dl[ei][:3,:3]=dl[ei][:3,:3]@R.from_euler('z',-elbow_delta,degrees=True).as_matrix()
    dl[wi][:3,:3]=dl[wi][:3,:3]@R.from_euler('z',wrist_delta,degrees=True).as_matrix()
runtime=lua.execute((ROOT/'scripts/mods/RoshiaReplacement/proportion_rig.lua').read_text())
jmodule=lua.execute((ROOT/'scripts/mods/RoshiaReplacement/roshia_jiggle.lua').read_text())
jconfig=lua.execute((OUT/'Custom/roshia_jiggle_bones.lua').read_text())
report={}
for label,asset in [('body','roshia'),('arms','roshia_arms')]:
    bind=np.array(fixture[asset]['world']).reshape(-1,4,4).transpose(0,2,1)
    parents=fixture[asset]['parents'];locals_=localize(bind,parents);stale=bind.copy()
    source_world=native.copy()
    aliases={d.get('target_name',d['name']):names[d['name']] for d in config[label]['bones']}
    U=lua.table();U.alive=lambda u:True;U.has_node=lambda u,n:n in names or (u=='target' and n in aliases);U.node=lambda u,n:(aliases[n] if u=='target' and n in aliases else names[n])+1
    U.world_position=lambda u,i:vec((source_world if u=='driver' else stale)[i-1,:3,3])
    U.world_rotation=lambda u,i:quat(R.from_matrix((source_world if u=='driver' else stale)[i-1,:3,:3]).as_quat())
    U.local_position=lambda u,i:vec(locals_[i-1][:3,3])
    U.local_rotation=lambda u,i:quat(R.from_matrix(locals_[i-1][:3,:3]).as_quat())
    def setpos(u,i,p):locals_[i-1][:3,3]=arr(p)
    def setrot(u,i,q):locals_[i-1][:3,:3]=R.from_quat(qa(q)).as_matrix()
    def setscale(u,i,s):
        matrix=locals_[i-1][:3,:3]
        locals_[i-1][:3,:3]=matrix/np.linalg.norm(matrix,axis=0)*arr(s)
    U.set_local_position=setpos;U.set_local_rotation=setrot;U.set_local_scale=setscale;lua.globals().Unit=U
    jiggle=jmodule.new(lambda k:1 if k!='jiggle_hang' else .15,jconfig)
    cfg=lua.table_from(config[label],recursive=True)
    wrist_error=0.;finger_overrun=0.;tail_length_error=0.;max_extension=1.;max_contact_shift=0.;max_wrist_rotation_error=0.
    native_hand_matrix_error=0.;source_hand_rotation_error=0.;source_hand_length_error=0.
    shoulder_endpoint_error=0.;shoulder_root_error=0.;support_scale_min=1.;support_scale_max=1.
    ik_names={n for c in config[label].get('grip_chains',[]) for n in c['names'][:2]}
    contact_error=0.;contact_before=[];contact_after=[];unreachable=0;contact_samples=0;contact_regression=0.
    poses_to_test=opts.cases or ['rest','idle','sword','grip','extreme','motion','run','rifle','pistol','reload','guard','swing','reach','oraxia_rifle','staff','shield','dual_blades','heavy_rifle','two_hand_axe','greatsword','psyker_charge','psyker_release','rapid_finger_motion']
    for case in poses_to_test:
        dl=localize(native,pars)
        if case not in ('rest','grip','extreme'):
            for side,sign in [('left',-1),('right',1)]:
                direction=[sign*.18,.06,-1.];elbow_delta=0;wrist_delta=0
                if case=='sword' and side=='right':direction=[.7,.05,.25];elbow_delta=35
                if case=='rifle':direction=[sign*.45,.65,-.6];elbow_delta=15
                if case=='pistol':direction=[sign*.15,.95,-.25];elbow_delta=-40
                if case=='reload':direction=[sign*.35,.4,-.55];elbow_delta=60 if side=='left' else 30;wrist_delta=15
                if case=='guard':direction=[sign*.5,.4,.25];elbow_delta=50
                if case=='swing':direction=[-sign*.5,.8,.1];elbow_delta=5
                if case=='reach':direction=[sign*.6,.1,.9];elbow_delta=-55
                if case=='staff':
                    direction=[.9,.1,-.15] if side=='right' else [-.35,.25,-.7]
                    elbow_delta=0 if side=='right' else 45;wrist_delta=0 if side=='right' else -25
                if case=='shield':direction=[sign*.4,.45,-.5];elbow_delta=25 if side=='left' else -15
                if case=='dual_blades':direction=[sign*.35,.1,-.9];elbow_delta=-25;wrist_delta=20*sign
                if case=='heavy_rifle':direction=[sign*.6,.6,-.3];elbow_delta=30
                if case=='two_hand_axe':direction=[sign*.5,.15,-.65];elbow_delta=10 if side=='left' else -10
                if case=='greatsword' and side=='right':direction=[.65,.1,.6];elbow_delta=50;wrist_delta=-20
                if case in ('psyker_charge','psyker_release','rapid_finger_motion'):
                    direction=[sign*.4,.65,-.4];elbow_delta=35;wrist_delta=sign*20
                set_arm_direction(dl,side,direction,elbow_delta,wrist_delta)
        if case=='oraxia_rifle':
            # Oraxia FLOAT_ARM_POSES.rifle key 1, in its torso right/forward/up
            # basis. Reference input only; no weapon-specific runtime preset.
            reference={'left':[(.166,.950,-.266),(.655,.537,.531),(.872,.486,-.054)],
                       'right':[(.650,.210,-.731),(-.631,.425,.649),(-.004,.994,.105)]}
            for side,vectors in reference.items():
                ids=[names['j_'+side+k]for k in ('arm','forearm','hand','handmiddle1')]
                for k,want in enumerate(vectors):
                    worlds=fk(dl,pars);i=ids[k];child=ids[k+1]
                    rot=turn(worlds[child,:3,3]-worlds[i,:3,3],np.array(want))@worlds[i,:3,:3]
                    dl[i][:3,:3]=worlds[pars[i],:3,:3].T@rot
        if case in ('grip','extreme','sword','rifle','pistol','reload','guard','swing','oraxia_rifle','staff','shield','dual_blades','heavy_rifle','two_hand_axe','greatsword'):
            for d in config[label]['bones']:
                n=d['name']
                if d['finger'] and 'inhand' not in n:
                    angle=(40 if n.endswith('1') else 55) if case!='extreme' else 135
                    if 'thumb' in n:angle=25 if case!='extreme' else 100
                    if case=='staff' and 'left' in n:angle=-10 if n.endswith('1') else 10
                    if case=='shield' and 'left' in n:angle=65
                    dl[names[n]][:3,:3]=dl[names[n]][:3,:3]@R.from_euler('z',angle,degrees=True).as_matrix()
        source_world=fk(dl,pars)
        if case in ('psyker_charge','psyker_release'):
            # Synthetic independent flexion/splay/opposition, not a captured
            # game ability. Transfer must preserve all axes without damping.
            for d in config[label]['bones']:
                if d['finger']:
                    n=d['name'];i=names[n];side_sign=-1 if 'left' in n else 1
                    angles=([side_sign*25,15,35] if 'thumb' in n else
                            [side_sign*5,8,(-12 if n.endswith('1') else 45)])
                    if case=='psyker_release':angles=[-a*.5 for a in angles]
                    dl[i][:3,:3]=dl[i][:3,:3]@R.from_euler('xyz',angles,degrees=True).as_matrix()
            source_world=fk(dl,pars)
        source_base=source_world.copy()
        for frame in range(20):
            if case=='run':
                # Synthetic alternating gait with torso twist, not a game clip.
                gait=[x.copy() for x in dl]
                phase=2*math.pi*frame/20
                for side,sign in [('left',-1),('right',1)]:
                    for suffix,angles in [('upleg',[sign*28*math.sin(phase),0,0]),
                                          ('leg',[max(0,sign*math.sin(phase))*35,0,0]),
                                          ('arm',[sign*-20*math.sin(phase),0,0])]:
                        i=names['j_'+side+suffix]
                        gait[i][:3,:3]=gait[i][:3,:3]@R.from_euler('xyz',angles,degrees=True).as_matrix()
                for suffix in ('spine','spine1','spine2'):
                    i=names['j_'+suffix]
                    gait[i][:3,:3]=gait[i][:3,:3]@R.from_euler('xyz',[3,0,4*math.sin(phase)],degrees=True).as_matrix()
                gait[0][:3,3]+=[frame*.025,0,.015*(1-math.cos(phase*2))]
                source_world=fk(gait,pars)
            if case=='rapid_finger_motion':
                rapid=[x.copy() for x in dl]
                for d in config[label]['bones']:
                    if d['finger']:
                        i=names[d['name']]
                        rapid[i][:3,:3]=rapid[i][:3,:3]@R.from_euler('xyz',[20*math.sin(frame),10*math.cos(frame),80 if frame%2 else -15],degrees=True).as_matrix()
                source_world=fk(rapid,pars)
            if case=='motion':
                motion=np.eye(4);motion[:3,:3]=R.from_euler('zyx',[frame*8,frame*.3,0],degrees=True).as_matrix()
                motion[:3,3]=[frame*.015,frame*-.01,0]
                source_world=np.einsum('ij,njk->nik',motion,source_base)
            if config[label].get('engine_linked'):
                locals_[0]=source_world[0].copy()
                for d in config[label]['bones']:
                    if d.get('engine_linked'):
                        i=names[d['name']];p=parents[i]
                        locals_[i]=np.linalg.inv(source_world[p])@source_world[i]
            poses=runtime.update('target','driver',cfg)
            contact_shift=arr(poses.contact_shift) if poses is not None else np.zeros(3)
            max_contact_shift=max(max_contact_shift,float(np.linalg.norm(contact_shift)))
            if poses is not None:
                jiggle.update('target',1/60,poses)
            posed=fk(locals_,parents)
            assert np.isfinite(posed).all()
            if case=='run' and frame in (0,5,10,15,19):
                (OUT/f'{label}_run_frame_{frame:02d}_pose.json').write_text(json.dumps({
                    'worlds':posed.tolist(),'driver_worlds':source_world.tolist(),'names':names,
                    'case':case,'frame':frame,'synthetic':True,
                    'description':'Production Lua output under a synthetic alternating gait; not a captured game animation.'}))
            for support in config[label].get('shoulder_supports',[]):
                si=names[support['name']];pi=names[support['parent']]
                ei=names[support['driver_elbow']];ci=names[support['driver_shoulder']]
                expected_root=(posed[pi,:3,3]+posed[pi,:3,:3]@support['clavicle_offset']
                    +source_world[ci,:3,:3]@support['arm_offset'])
                shoulder_root_error=max(shoulder_root_error,float(np.linalg.norm(posed[si,:3,3]-expected_root)))
                end=posed[si]@np.array([support['axis_sign']*support['rest_length'],0,0,1])
                shoulder_endpoint_error=max(shoulder_endpoint_error,float(np.linalg.norm(end[:3]-source_world[ei,:3,3])))
                axial_scale=float(np.linalg.norm(posed[si,:3,0]))
                support_scale_min=min(support_scale_min,axial_scale);support_scale_max=max(support_scale_max,axial_scale)
            for side in ('left','right'):
                i=names['j_'+side+'hand']
                wrist_error=max(wrist_error,float(np.linalg.norm(posed[i,:3,3]-source_world[i,:3,3]-contact_shift)))
                max_wrist_rotation_error=max(max_wrist_rotation_error,float(R.from_matrix(posed[i,:3,:3].T@source_world[i,:3,:3]).magnitude()))
            for d in config[label]['bones']:
                i=names[d['name']];p=parents[i]
                if d['native_position_driver']:
                    native_hand_matrix_error=max(native_hand_matrix_error,float(abs(posed[i]-source_world[i]).max()))
                if d.get('source_hand_fk') or (config[label].get('source_digit_lengths')
                        and d['finger'] and not d['native_position_driver']):
                    expected=source_world[i,:3,:3]@native[i,:3,:3].T@bind[i,:3,:3]
                    if d['name'] not in ik_names:
                        source_hand_rotation_error=max(source_hand_rotation_error,float(R.from_matrix(expected.T@posed[i,:3,:3]).magnitude()))
                    source_hand_length_error=max(source_hand_length_error,abs(float(np.linalg.norm(posed[i,:3,3]-posed[p,:3,3]))-np.linalg.norm(d['offset'])))
                if d['finger']:
                    rel=R.from_matrix(posed[p,:3,:3].T@posed[i,:3,:3])
                    rel=R.from_quat(d['rotation_pre']).inv()*rel*R.from_quat(d['rotation_post']).inv()
                    delta=rel*R.from_quat(d['native_rest_rotation']).inv()
                    finger_overrun=max(finger_overrun,float(np.rad2deg(delta.magnitude()))-d['angle_limit'])
            for r in json.loads((OUT/'Custom/roshia_jiggle_bones.json').read_text(encoding='utf-8'))['runtime_bones']:
                if r['group']=='tail':
                    i=names[r['node']];p=parents[i]
                    tail_length_error=max(tail_length_error,abs(np.linalg.norm(posed[i,:3,3]-posed[p,:3,3])-np.linalg.norm(bind[i,:3,3]-bind[p,:3,3])))
            for chain in config[label]['arm_chains']:
                ids=[names[n]for n in chain['names']]
                max_extension=max(max_extension,*[float(np.linalg.norm(posed[ids[k+1],:3,3]-posed[ids[k],:3,3])/chain['lengths'][k])for k in (0,1)])
            for chain in config[label].get('grip_chains',[]):
                i,j,k=[names[n] for n in chain['names']]
                a,b,c=posed[[i,j,k],:3,3];target=source_world[k,:3,3]
                l1,l2=chain['lengths'];distance=float(np.linalg.norm(target-a))
                optimum=max(0.,distance-l1-l2,abs(l1-l2)-distance)
                residual=float(np.linalg.norm(c-target))
                before_position=arr(poses.contact_before[chain['names'][2]])
                before_error=float(np.linalg.norm(before_position-target))
                contact_regression=max(contact_regression,residual-before_error)
                contact_before.append(before_error)
                contact_error=max(contact_error,abs(residual-optimum))
                assert abs(np.linalg.norm(b-a)-l1)<1e-6
                assert abs(np.linalg.norm(c-b)-l2)<1e-6
                contact_after.append(residual);unreachable+=int(optimum>1e-5);contact_samples+=1
            stale=posed.copy()
        mmr_worlds=posed.copy()
        if config[label].get('grip_chains'):
            saved_chains=cfg.grip_chains;cfg.grip_chains=lua.table()
            runtime.update('target','driver',cfg)
            mmr_worlds=fk(locals_,parents)
            cfg.grip_chains=saved_chains
        exports={'worlds':posed.tolist(),'case':case,'driver_worlds':source_world.tolist(),'names':names,'contact_shift':contact_shift.tolist(),
                 'mmr_worlds':mmr_worlds.tolist(),
                 'synthetic':True,'description':'Actual Lua native-driver/shoulder-support/jiggle output; synthetic actor pose, not a game capture.'}
        (OUT/f'{label}_{case}_pose.json').write_text(json.dumps(exports))
    assert wrist_error<1e-5,(label,wrist_error)
    assert finger_overrun<1e-3,(label,finger_overrun)
    assert tail_length_error<1e-5,(label,tail_length_error)
    assert max_extension<=1.121,(label,max_extension)
    assert max_wrist_rotation_error<1e-5,(label,max_wrist_rotation_error)
    assert max_contact_shift<1e-8
    assert native_hand_matrix_error<1e-5,(label,native_hand_matrix_error)
    assert source_hand_rotation_error<2e-5,(label,source_hand_rotation_error)
    assert source_hand_length_error<1e-6,(label,source_hand_length_error)
    assert shoulder_root_error<1e-5,(label,shoulder_root_error)
    assert shoulder_endpoint_error<1e-5,(label,shoulder_endpoint_error)
    assert contact_regression<2e-6,(label,contact_regression)
    report[label]={'wrist_target_error':wrist_error,'finger_limit_overrun_deg':finger_overrun,
                   'tail_local_length_error':tail_length_error,'maximum_arm_reach_scale':max_extension,'maximum_weapon_translation':max_contact_shift,
                   'wrist_rotation_error_radians':max_wrist_rotation_error,'native_hand_matrix_error':native_hand_matrix_error,
                   'source_hand_rotation_transfer_error':source_hand_rotation_error,'source_hand_segment_length_error':source_hand_length_error,
                   'shoulder_root_error':shoulder_root_error,'shoulder_endpoint_error':shoulder_endpoint_error,
                   'shoulder_support_scale_range':[support_scale_min,support_scale_max],
                   'frames':20*len(poses_to_test),'synthetic_cases':poses_to_test}
    report[label]['contact_solver']={'target':'native distal joint; not a weapon surface collision test',
        'max_distance_from_fixed_length_optimum_m':contact_error,
        'max_contact_error_increase_m':contact_regression,
        'mean_final_joint_error_m':float(np.mean(contact_after)) if contact_after else None,
        'mean_uncorrected_joint_error_m':float(np.mean(contact_before)) if contact_before else None,
        'unreachable_targets':unreachable,'samples':contact_samples}
    if config[label].get('engine_linked'):
        # The actor/camera can move after the Lua loadout update. Apply only
        # the named-node engine links, with NO second Lua FK update.
        move=np.eye(4);move[:3,:3]=R.from_euler('zyx',[75,-32,18],degrees=True).as_matrix()
        move[:3,3]=[.4,-.2,.15]
        source_world=np.einsum('ij,njk->nik',move,source_world)
        locals_[0]=source_world[0].copy()
        for d in config[label]['bones']:
            if d.get('engine_linked'):
                i=names[d['name']];p=parents[i]
                locals_[i]=np.linalg.inv(source_world[p])@source_world[i]
        late=fk(locals_,parents)
        late_error=max(float(abs(late[names['j_'+side+'hand']]-source_world[names['j_'+side+'hand']]).max())
                       for side in ('left','right'))
        assert late_error<1e-6,late_error
        if config[label].get('native_hand_contract'):
            all_finger_error=max(float(abs(late[names[d['name']]]-source_world[names[d['name']]]).max())
                                 for d in config[label]['bones'] if d['finger'])
            assert all_finger_error<1e-6,all_finger_error
            report[label]['late_camera_update_all_finger_matrix_error']=all_finger_error
        report[label]['late_camera_update_wrist_matrix_error']=late_error
    runtime.clear('target');jiggle.clear('target')
for f in (ROOT/'scripts/mods/RoshiaReplacement').glob('*.lua'):
    ok,err=lua.eval('function(s)local f,e=load(s);return f~=nil,e end')(f.read_text(encoding='utf-8-sig'))
    assert ok,(str(f),err)
# Exercise actual class_target Lua with the project class catalog. Ownership
# remains delegated to the registry; this test never changes user selections.
class_lua=LuaRuntime(unpack_returned_tuples=True)
class_lua.execute('get_mod=function(id) if id=="ModelReplacementRegistry" then return {api={version=2,owns=function(model,name,breed,surface) return name~="ogryn" and breed=="human" end}} end return {} end')
target=class_lua.execute((ROOT/'scripts/mods/RoshiaReplacement/class_target.lua').read_text(encoding='utf-8'))
catalog=class_lua.execute((ROOT/'scripts/mods/AnimeModelReplacement/model_definitions.lua').read_text(encoding='utf-8'))
classes=[]
for _,entry in catalog.classes.items():
    name=entry.id
    profile=class_lua.table_from({'archetype':class_lua.table_from({'name':name,'breed':'human'})})
    ext=class_lua.table_from({'_static_profile_properties':class_lua.table_from({'archetype':name,'breed':'human'})})
    assert target.profile_matches(profile),name
    assert target.extension_matches(ext),name
    classes.append(name)
ogryn=class_lua.table_from({'archetype':class_lua.table_from({'name':'ogryn','breed':'ogryn'})})
assert not target.profile_matches(ogryn)
report['profession_routing']={'human_classes':sorted(classes),'ogryn_excluded':True,'scope':'selection/driver routing, not captured weapon animations'}
(OUT/'contact_runtime_audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
