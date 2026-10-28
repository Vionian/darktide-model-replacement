"""Execute the production portrait hook and project its bounds through camera FOV."""
import pathlib,sys,json,math
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/model-work/python-deps'))
from lupa.luajit21 import LuaRuntime

lua=LuaRuntime(unpack_returned_tuples=True)
lua.globals().read=lambda p:(ROOT/(p.removeprefix('AnimeModelReplacement/')+'.lua')).read_text(encoding='utf-8')
lua.execute('''
local mt={};mt.__index=mt
function vec(x,y,z)return setmetatable({x=x,y=y,z=z},mt)end
mt.__add=function(a,b)return vec(a.x+b.x,a.y+b.y,a.z+b.z)end
mt.__sub=function(a,b)return vec(a.x-b.x,a.y-b.y,a.z-b.z)end
mt.__mul=function(a,n)return vec(a.x*n,a.y*n,a.z*n)end
Vector3=setmetatable({dot=function(a,b)return a.x*b.x+a.y*b.y+a.z*b.z end},{__call=function(_,...)return vec(...)end})
Quaternion={rotate=function(q,v)return vec(q[1][1]*v.x+q[1][2]*v.y+q[1][3]*v.z,q[2][1]*v.x+q[2][2]*v.y+q[2][3]*v.z,q[3][1]*v.x+q[3][2]*v.y+q[3][3]*v.z)end}
Unit={alive=function(u)return u.alive end,has_node=function(u)return u.has_head end,node=function()return 1 end,
      world_position=function(u)return u.position end,world_rotation=function(u)return u.rotation end}
Camera={vertical_fov=function(c)return c.fov end}
CLASS={PortraitUI={}}
owner={}
function owner:io_dofile(p)return assert(loadstring(read(p)))()end
function owner:hook(c,n,f)assert(c==CLASS.PortraitUI and n=='_is_ready_to_capture_request');hook=f end
identity={{1,0,0},{0,1,0},{0,0,1}}
function fresh(asset,aspect)
 local u={alive=true,has_head=true,position=vec(0,0,1.6),rotation=identity}
 local world={pos=vec(0,-1,1.6),calls=0,camera_data={fov=math.rad(35)}}
 function world:camera()return self.camera_data end
 function world:camera_rotation()return identity end
 function world:set_camera_position(p)self.pos=p;self.calls=self.calls+1 end
 return {_render_settings={world_name='portrait_world',width=140,height=160},_active_request={size={160*aspect,160}},
  _profile_spawner={__anime_portrait_subject={unit=u,asset=asset}},_world_spawner=world}
end
''')
lua.execute((ROOT/'scripts/mods/AnimeModelReplacement/portrait_framing.lua').read_text(encoding='utf-8')).install(lua.globals().owner)
bounds=lua.execute((ROOT/'scripts/mods/AnimeModelReplacement/portrait_bounds.lua').read_text())
rows=[]
for asset,spec in bounds.items():
    count=0
    for aspect in (.875,1.,1.25):
        for angle in (-25,0,25):
            s=lua.globals().fresh(asset,aspect)
            unit=s._profile_spawner.__anime_portrait_subject.unit
            c,t=math.cos(math.radians(angle)),math.sin(math.radians(angle))
            unit.rotation=lua.table_from([lua.table_from([c,0,t]),lua.table_from([0,1,0]),lua.table_from([-t,0,c])])
            assert lua.globals().hook(lambda *_:True,s)
            p=s._world_spawner.pos
            first=(p.x,p.y,p.z)
            assert lua.globals().hook(lambda *_:True,s)
            assert first==(s._world_spawner.pos.x,s._world_spawner.pos.y,s._world_spawner.pos.z),'Camera accumulated an offset'
            for x in (1,2):
                for y in (1,2):
                    for z in (1,2):
                        v=lua.globals().vec(spec[x][1],spec[y][2],spec[z][3])
                        v=lua.globals().Quaternion.rotate(unit.rotation,v)
                        wx,wy,wz=v.x+unit.position.x,v.y+unit.position.y,v.z+unit.position.z
                        depth=wy-p.y
                        assert depth>.01
                        assert abs((wx-p.x)/(depth*math.tan(math.radians(17.5))*aspect))<=.800001
                        assert abs((wz-p.z)/(depth*math.tan(math.radians(17.5))))<=.800001
            count+=1
    rows.append({'asset':asset,'projected_cases':count,'all_head_corners_inside_80_percent':True})
lua.execute('''
for _,kind in ipairs({'cosmetics','focus','endround','no_subject','deleted','missing_node','not_ready'})do
 local s=fresh('roshia',.875)
 if kind=='cosmetics'then s._render_settings.world_name='cosmetics_portrait_world';s._always_render=true end
 if kind=='focus'then s._active_request.render_context={camera_focus_slot_name='slot_head'}end
 if kind=='endround'then s._active_request.render_context={use_end_of_round_camera=true}end
 if kind=='no_subject'then s._profile_spawner=nil end
 if kind=='deleted'then s._profile_spawner.__anime_portrait_subject.unit.alive=false end
 if kind=='missing_node'then s._profile_spawner.__anime_portrait_subject.unit.has_head=false end
 local ready=kind~='not_ready'
 assert(hook(function()return ready end,s)==ready)
 assert(s._world_spawner.calls==0,kind)
end
''')
report={'models':rows,'cases':sum(x['projected_cases'] for x in rows),'repeated_capture_no_camera_drift':True,
        'cosmetics_and_special_cameras_untouched':True,'missing_and_dead_subject_safe':True,'game_launched':False}
(ROOT/'tools/model-work/distribution_fix/portrait_framing_checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PORTRAIT_FRAMING_OK',len(rows),report['cases'])
