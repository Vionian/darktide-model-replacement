local root = assert(arg[1], 'pass project root')
local folder = root .. '/WeaponModelReplacement/'
local runtime = folder .. 'scripts/mods/WeaponModelReplacement/'
local passed = {}
local function check(name, test)
    test()
    passed[#passed + 1] = name
    print('PASS ' .. name)
end
local hooks, safe, require_callback, queued, units = {}, {}, nil, {}, {}
local settings = {skin_scope='all', emission_strength=1,skin_psyker_forcesword_2h='langzhifei'}
local enabled, callback, ticket, released, next_id = true, nil, nil, 0, 0
local counts = {spawn=0, link=0, native=0, mark=0, warnings=0}
local mod = {}
function mod:get(key) return settings[key] end
function mod:set(key,value) settings[key]=value end
function mod:is_enabled() return enabled end
function mod:localize(key, ...) return key end
function mod:info(...) end
function mod:warning(...) counts.warnings=counts.warnings+1 end
function mod:echo(...) end
function mod:io_dofile(path) return dofile(root .. '/' .. path .. '.lua') end
function mod:hook(target,name,fn)
    hooks[target]=hooks[target] or {}; assert(not hooks[target][name], 'duplicate hook')
    hooks[target][name]=fn
end
function mod:hook_safe(target,name,fn) safe[target]=safe[target] or {}; safe[target][name]=fn end
function mod:hook_enable(...) end
function mod:hook_require(path,fn) require_callback=fn end
function mod:command(name,help,fn) self.command=fn end
local api = {
    is_api_compatible=function(v) return v==1 end,
    can_get_resource=function(kind,path) return true end,
    acquire=function(owner,id,fn,options)
        assert(id=='WeaponModelReplacement:khravengger'); callback=fn; ticket={id=id}; return ticket
    end,
    release=function(t) assert(t==ticket); released=released+1 end,
}
function get_mod(name) if name=='CustomAssets' then return api end; return mod end
Managers={package={},world={_worlds={},_disabled_worlds={}}}
VisibilityContexts={SHADOW_CASTER_CONTEXT=1,RAYTRACING_CONTEXT=2}
function Vector3(x,y,z) return {x,y,z} end
Matrix4x4={identity=function() return {identity=true} end}
local function new_unit(world,name)
    next_id=next_id+1
    local u={world=world,name=name,alive=true,id=next_id,visible=true,scalars={},vectors={}}
    units[#units+1]=u; return u
end
Unit={
    alive=function(u) assert(not u.world.dead,'queried a destroyed world'); return u.alive end,
    get_data=function(u,key) return u.name end,
    world_pose=function(u,node) return {native_pose=true} end,
    set_unit_objects_visibility=function(u,visible,recursive,context)
        assert(recursive==false or context==VisibilityContexts.RAYTRACING_CONTEXT)
        if not context then u.visible=visible end
    end,
    set_mesh_visibility=function(u,name,visible) u.fx_visible=visible end,
    set_unit_visibility=function(u,visible) u.visible=visible end,
    set_scalar_for_material=function(u,slot,key,value) assert(slot=='khravengger_pbr');u.scalars[key]=value end,
    set_vector3_for_material=function(u,slot,key,value) u.vectors[key]=value end,
    set_local_pose=function(u,node,pose) assert(pose.identity); u.identity=true end,
    set_unit_culling=function(u,v) u.culling=v end,
    set_shader_pass_flag_for_meshes_in_unit_and_childs=function(u,name,v) u.fov=v end,
}
World={LINK_MODE_NONE=0}
function World.spawn_unit_ex(world,name,_,pose)
    counts.spawn=counts.spawn+1
    assert(name=='content/mods/weapon_model_replacement/khravengger')
    return new_unit(world,name)
end
function World.link_unit(world,visual,node,driver,driver_node,mode)
    counts.link=counts.link+1
    assert(driver.is_weapon_root and mode==0,'native player/equipment was reparented')
    visual.parent=driver
end
function World.destroy_unit(world,u) assert(not world.dead);u.alive=false end
local spawner={}
function spawner:spawn_unit(name,pose) return World.spawn_unit_ex(self._world,name,nil,pose) end
function spawner:mark_for_deletion(u)
    return hooks.UnitSpawnerManager.mark_for_deletion(function(self,u)
    assert(not u.queued,'double deletion');u.queued=true;queued[#queued+1]=u;counts.mark=counts.mark+1
    end,self,u)
end
local function flush() for _,u in ipairs(queued) do u.alive=false end;queued={} end
local prefix='content/weapons/player/melee/2h_force_sword/attachments/'
local one_h_prefix='content/weapons/player/melee/force_sword/attachments/'
local function item(mark) return {weapon_template=mark or 'forcesword_2h_p1_m1', slot_weapon_skin={name='native_default'},charge=2} end
local function fixture(first_person)
    local world={}
    Managers.world._worlds[#Managers.world._worlds+1]=world
    local unit=new_unit(world,'base');unit.is_weapon_root=true
    local original={}
    for _,name in ipairs({'grip_03/grip_ml01','hilt_ml01/hilt_ml01','blade_ml01/blade_ml01','pommel_ml01/pommel_ml01'}) do
        original[#original+1]=new_unit(world,prefix..name)
    end
    local charm=new_unit(world,'content/items/trinket')
    local trail=new_unit(world,prefix..'trail_01/trail_01')
    local map={[unit]={}}
    for _,u in ipairs(original) do map[unit][#map[unit]+1]=u end
    map[unit][#map[unit]+1]=charm;map[unit][#map[unit]+1]=trail
    local instance=setmetatable({_world=world},{__index=spawner})
    return {world=world,root=unit,original=original,charm=charm,trail=trail,map=map,
        settings={world=world,is_first_person=first_person,unit_spawner=instance},item=item()}
end
local target={}
local function spawn(f)
    return hooks[target].spawn_item(function(it,options) counts.native=counts.native+1;return f.root,f.map,'tail',nil end,f.item,f.settings)
end
local function refresh(f)
    return hooks[target].spawn_item_attachments(function(...) return f.map,'attachment-tail',nil end,f.item,{},f.settings,f.root)
end
local function visual(f)
    for _,u in ipairs(f.map[f.root]) do if u.name=='content/mods/weapon_model_replacement/khravengger' and u.alive then return u end end
end
dofile(runtime..'WeaponModelReplacement.lua')
mod.on_all_mods_loaded();require_callback(target)
check('legacy Langzhifei selection migrates to ordinary force sword',function()
    assert(settings.skin_psyker_forcesword_2h=='khravengger')
    assert(settings.skin_psyker_forcesword_1h=='langzhifei')
end)
local S=dofile(runtime..'selection.lua')
check('ordinary force sword uses Langzhifei while greatsword uses Khravengger',function()
    assert(S.profile(item('forcesword_p1_m1')).id=='langzhifei')
    assert(S.profile(item('forcesword_p1_m2')).id=='langzhifei')
    assert(S.profile(item('forcesword_p1_m3')).id=='langzhifei')
    assert(S.profiles.langzhifei_force.prefix==one_h_prefix)
    assert(S.matches(item('forcesword_2h_p1_m1'),'all'))
    assert(S.matches(item('forcesword_2h_p1_m2'),'all'))
    assert(not S.matches(item('powersword_p1_m1'),'all'))
end)
check('ordinary and two-handed Psyker selections are independent',function()
    settings.skin_psyker_forcesword_1h='none';assert(not S.matches(item('forcesword_p1_m1'),'all'))
    settings.skin_psyker_forcesword_1h='langzhifei';assert(S.profile(item('forcesword_p1_m3')).id=='langzhifei')
    settings.skin_psyker_forcesword_2h='none';assert(not S.matches(item('forcesword_2h_p1_m1'),'all'))
    settings.skin_psyker_forcesword_2h='khravengger'
end)
check('Zealot relic sword selects Khravengger independently',function()
    settings.skin_zealot_relicsword_2h='khravengger'
    assert(S.profile(item('powersword_2h_p1_m1')).id=='khravengger')
    settings.skin_zealot_relicsword_2h='none';assert(not S.matches(item('powersword_2h_p1_m1'),'all'))
    settings.skin_zealot_relicsword_2h='khravengger'
end)
check('reference skin restriction',function()
    assert(not S.matches(item(),'reference'))
    local it=item();it.slot_weapon_skin=S.reference_skin;assert(S.matches(it,'reference'))
end)
check('native parts exclude trails trinkets and foreign weapons',function()
    assert(S.part_kind(prefix..'blade_01/blade_01')=='blade')
    assert(not S.part_kind(prefix..'trail_01/trail_01'))
    assert(not S.part_kind('content/items/trinket'))
    assert(S.part_kind(one_h_prefix..'blade_01/blade_01')=='blade')
end)
local first=fixture(true)
check('pending resource loading preserves native sword',function()
    local a,b,c,d=spawn(first);assert(a==first.root and b==first.map and c=='tail' and d==nil)
    assert(not visual(first));for _,u in ipairs(first.original) do assert(u.visible) end
end)
check('late resource callback attaches pending sword',function()
    callback(ticket,{},nil);mod.update(.01)
    assert(visual(first));for _,u in ipairs(first.original) do assert(not u.visible) end
    assert(first.charm.visible and first.trail.visible and first.item.charge==2)
end)
check('first person attachment uses native root FOV and culling',function()
    local v=visual(first);assert(v.parent==first.root and v.identity and v.fov and v.culling==false)
    assert(v.vectors.emissive_color[1]==1 and v.scalars.intensity==.25)
end)
check('repeated attachment refresh is idempotent',function()
    local v=visual(first);local before=counts.spawn
    for _=1,4 do local a,b=refresh(first);assert(a==first.map and b=='attachment-tail') end
    assert(counts.spawn==before and visual(first)==v)
end)
check('require callback installs each actual module only once',function()
    require_callback(target);assert(hooks[target].spawn_item)
end)
local third=fixture(false);third.item=item('forcesword_2h_p1_m2')
check('third person and preview path',function()
    spawn(third);assert(visual(third).parent==third.root and not visual(third).fov)
end)
check('unrelated weapon retains native appearance',function()
    local f=fixture(true);f.item=item('chainsword_p1_m1');spawn(f)
    assert(not visual(f));for _,u in ipairs(f.original) do assert(u.visible) end
end)
check('partial incompatible custom attachment is not hidden',function()
    local f=fixture(true);table.remove(f.map[f.root],3);spawn(f)
    assert(not visual(f));assert(f.original[1].visible)
end)
check('setting change updates source emission color unchanged',function()
    settings.emission_strength=.37;mod.on_setting_changed('emission_strength')
    assert(visual(first).scalars.intensity==.37*.25 and visual(first).vectors.emissive_color[3]==1)
end)
check('disable restores original models and defers package release',function()
    enabled=false;mod.on_disabled();assert(not visual(first));assert(released==0)
    for _,u in ipairs(first.original) do assert(u.visible) end
    flush();mod.update(.01);assert(released==1)
end)
check('re-enable restores already spawned equipment',function()
    enabled=true;mod.on_enabled();callback(ticket,{},nil);mod.update(.01)
    assert(visual(first) and visual(third))
end)
check('legacy hidden scope cannot override the weapon dropdown',function()
    settings.skin_scope='reference';mod.on_setting_changed('skin_scope');mod.update(.01)
    assert(visual(first));assert(not first.original[1].visible)
    settings.skin_scope='all';first.item.slot_weapon_skin=S.reference_skin;spawn(first);assert(visual(first))
end)
check('skin dropdown selects original and restores Khravengger on same root',function()
    settings.skin_psyker_forcesword_2h='none';mod.on_setting_changed('skin_psyker_forcesword_2h');mod.update(.01)
    assert(not visual(first) and first.original[1].visible)
    settings.skin_psyker_forcesword_2h='khravengger';mod.on_setting_changed('skin_psyker_forcesword_2h');spawn(first);assert(visual(first))
end)
check('native deletion queue avoids duplicate deletion',function()
    local v=visual(first);first.settings.unit_spawner:mark_for_deletion(v)
    local before=counts.mark;mod.update(.01);assert(counts.mark==before);flush();mod.update(.01)
end)
check('attachment-only replacement handles retained root',function()
    for i=1,4 do first.map[first.root][i]=new_unit(first.world,prefix..({'grip_03/grip_ml01','hilt_ml01/hilt_ml01','blade_ml01/blade_ml01','pommel_ml01/pommel_ml01'})[i]) end
    refresh(first);assert(visual(first))
end)
check('world destruction forgets every active and pending handle',function()
    hooks.WorldManager.destroy_world(function(_,world) world.dead=true end,{},first.world)
    mod.update(.01)
end)
check('toggle after world destruction has no stale engine access',function()
    enabled=false;mod.on_disabled();flush();mod.update(.01)
end)
check('unload restores any remaining visual without releasing live tickets',function()
    enabled=true;mod.on_enabled();callback(ticket,{},nil);mod.update(.01)
    local f=fixture(true);spawn(f);assert(visual(f));mod.on_unload(false)
    assert(f.original[1].visible and not visual(f))
end)
print('RUNTIME_TESTS_OK '..#passed)
