"""Execute the actual runtime Lua against a numerical Unit/Quaternion shim.

Checks arbitrary actor motion, bone lengths, 1P wrist anchors and curl limits.
Does not start or connect to the game.
"""
import json, pathlib, sys, math
import numpy as np
from scipy.spatial.transform import Rotation
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/model-work/python-deps'))
from lupa import LuaRuntime
OUT=pathlib.Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'tools/model-work/roshia/iter_20261018_source_hand_candidate'
fixture=json.loads((OUT/'runtime_fixture.json').read_text())
config=json.loads((OUT/'Custom/roshia_proportion_bones.json').read_text())
lua=LuaRuntime(unpack_returned_tuples=True)
lua.execute('''
math.atan2 = math.atan
local vector3={}
local mt={}
mt.__add=function(a,b)return vector3(a.x+b.x,a.y+b.y,a.z+b.z)end
mt.__sub=function(a,b)return vector3(a.x-b.x,a.y-b.y,a.z-b.z)end
mt.__mul=function(a,b)return vector3(a.x*b,a.y*b,a.z*b)end
mt.__div=function(a,b)return vector3(a.x/b,a.y/b,a.z/b)end
setmetatable(vector3,{__call=function(_,x,y,z)return setmetatable({x=x,y=y,z=z},mt)end})
vector3.length=function(a)return math.sqrt(a.x*a.x+a.y*a.y+a.z*a.z)end
vector3.dot=function(a,b)return a.x*b.x+a.y*b.y+a.z*b.z end
vector3.cross=function(a,b)return vector3(a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x)end
Vector3=vector3
Quaternion={}
''')
def vec(a):return lua.globals().Vector3(*[float(x) for x in a])
def arr(v):return np.array([v.x,v.y,v.z],float)
def quat(q):return lua.table_from(dict(x=float(q[0]),y=float(q[1]),z=float(q[2]),w=float(q[3])))
def qa(q):return np.array([q.x,q.y,q.z,q.w],float)
Q=lua.globals().Quaternion
Q.identity=lambda:quat([0,0,0,1])
Q.from_elements=lambda x,y,z,w:quat([x,y,z,w])
Q.to_elements=lambda q:tuple(qa(q))
Q.inverse=lambda q:quat(Rotation.from_quat(qa(q)).inv().as_quat())
Q.multiply=lambda a,b:quat((Rotation.from_quat(qa(a))*Rotation.from_quat(qa(b))).as_quat())
def qslerp(a,b,t):
    first,second=qa(a),qa(b)
    dot=float(np.dot(first,second))
    if dot<0:
        second=-second;dot=-dot
    if dot>0.9995:
        value=first+(second-first)*t
        return quat(value/np.linalg.norm(value))
    angle=math.acos(max(-1.0,min(1.0,dot)))
    value=(math.sin((1-t)*angle)*first+math.sin(t*angle)*second)/math.sin(angle)
    return quat(value)
Q.slerp=qslerp
Q.rotate=lambda q,v:vec(Rotation.from_quat(qa(q)).apply(arr(v)))
Q.axis_angle=lambda v,a:quat(Rotation.from_rotvec(arr(v)*a).as_quat())
native=np.array(fixture['template_world']).reshape(-1,4,4).transpose(0,2,1)
names=fixture['names']; pars=fixture['parents']
def matrix(q,p):
    m=np.eye(4);m[:3,:3]=Rotation.from_quat(q).as_matrix();m[:3,3]=p;return m
def recurse(worlds,parents,locals_,i):
    if i not in worlds:
        p=parents[i]
        worlds[i]=locals_[i] if p<0 else recurse(worlds,parents,locals_,p)@locals_[i]
    return worlds[i]
runtime=lua.execute((ROOT/'scripts/mods/RoshiaReplacement/proportion_rig.lua').read_text())
report={}
for label,asset in [('body','roshia'),('arms','roshia_arms')]:
    target=np.array(fixture[asset]['world']).reshape(-1,4,4).transpose(0,2,1)
    target_par=fixture[asset]['parents']
    locals_=[np.linalg.inv(target[p])@w if p>=0 else w.copy() for p,w in zip(target_par,target)]
    source_world=native.copy()
    U=lua.table()
    U.alive=lambda u:True
    aliases={d.get('target_name',d['name']):names[d['name']] for d in config[label]['bones']}
    U.has_node=lambda u,n:n in names or (u=='target' and n in aliases)
    U.node=lambda u,n:(aliases[n] if u=='target' and n in aliases else names[n])+1
    U.world_position=lambda u,i:vec((source_world if u=='source' else target)[i-1,:3,3])
    U.world_rotation=lambda u,i:quat(Rotation.from_matrix((source_world if u=='source' else target)[i-1,:3,:3]).as_quat())
    def setpos(u,i,p):locals_[i-1][:3,3]=arr(p)
    def setrot(u,i,q):locals_[i-1][:3,:3]=Rotation.from_quat(qa(q)).as_matrix()
    U.set_local_position=setpos;U.set_local_rotation=setrot;U.set_local_scale=lambda u,i,s:None
    lua.globals().Unit=U
    cfg=lua.table_from(config[label],recursive=True)
    # This fixture isolates rest-axis/FK transfer. The contact solver is
    # separately exercised against reachable and unreachable native targets.
    cfg.grip_chains=lua.table()
    max_rest=max_length=max_wrist=max_limit=0.
    for frame in range(6):
        driver_local=[np.linalg.inv(native[p])@w if p>=0 else w.copy() for p,w in zip(pars,native)]
        root=matrix(Rotation.from_euler('zyx',[frame*17,frame*2,0],degrees=True).as_quat(),[frame*.2,-frame*.1,.05*frame])
        driver_local[0]=root@driver_local[0]
        for n,i in names.items():
            if n.endswith('forearm') and frame:
                driver_local[i][:3,:3]=driver_local[i][:3,:3]@Rotation.from_euler('z',frame*7,degrees=True).as_matrix()
            if 'hand' in n and n[-1:] in ('1','2','3') and frame:
                driver_local[i][:3,:3]=driver_local[i][:3,:3]@Rotation.from_euler('z',frame*27,degrees=True).as_matrix()
        cache={};source_world=np.array([recurse(cache,pars,driver_local,i) for i in range(len(native))])
        if config[label].get('engine_linked'):
            locals_[0]=source_world[0].copy()
            for d in config[label]['bones']:
                if d.get('engine_linked'):
                    i=names[d['name']];p=target_par[i]
                    locals_[i]=np.linalg.inv(source_world[p])@source_world[i]
        runtime.update('target','source',cfg)
        cache={};posed=np.array([recurse(cache,target_par,locals_,i) for i in range(len(target))])
        for d in config[label]['bones']:
            i=names[d['name']];p=d['parent_index']
            if frame==0:max_rest=max(max_rest,float(abs(posed[i]-target[i]).max()))
            if d['native_position_driver']:
                max_wrist=max(max_wrist,float(np.linalg.norm(posed[i,:3,3]-source_world[i,:3,3])))
            elif d['name']!='j_hips':
                max_length=max(max_length,abs(float(np.linalg.norm(posed[i,:3,3]-posed[p,:3,3]))-np.linalg.norm(d['offset'])))
            if d['finger']:
                relative=Rotation.from_matrix(posed[p,:3,:3].T@posed[i,:3,:3])
                native_relative=Rotation.from_quat(d['rotation_pre']).inv()*relative*Rotation.from_quat(d['rotation_post']).inv()
                delta=native_relative*Rotation.from_quat(d['native_rest_rotation']).inv()
                max_limit=max(max_limit,float(np.rad2deg(delta.magnitude()))-d['angle_limit'])
        target=posed
    assert max_rest<1e-4,(label,max_rest)
    assert max_length<1e-5,(label,max_length)
    assert max_wrist<1e-4,(label,max_wrist)
    assert max_limit<1e-3,(label,max_limit)
    report[label]={'rest_matrix_error':max_rest,'bone_length_error':max_length,'wrist_anchor_error':max_wrist,'curl_limit_overrun_degrees':max_limit,'frames':6}
    runtime.clear('target')
(OUT/'runtime_audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
for file in (ROOT/'scripts/mods/RoshiaReplacement').glob('*.lua'):
    result=lua.eval('function(s) local f,e=load(s);return f~=nil,e end')(file.read_text(encoding='utf-8-sig'))
    assert result[0],(str(file),result[1])
print('LUA_SYNTAX_OK')
