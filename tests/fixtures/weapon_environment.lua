-- Original synthetic engine mock: no game source or assets required.
e = {hooks={},worlds={},queued={},enabled=true,spawns=0,releases=0,settings={}}
mod = {}
function mod:get(key) return e.settings[key] end
function mod:is_enabled() return e.enabled end
function mod:localize(key) return key end
function mod:info() end
function mod:warning() end
function mod:echo() end
function mod:command() end
function mod:hook(target,name,fn)
    e.hooks[target]=e.hooks[target] or {}; e.hooks[target][name]=fn
end
function mod:hook_safe(target,name,fn) self:hook(target,name,fn) end
function mod:hook_enable() end
function mod:hook_require(_,fn) e.install=fn end
function mod:io_dofile(path)
    local name=path:match('/([^/]+)$')
    return assert(loadstring(read_module(name)))()
end
local api = {}
function api.is_api_compatible() return true end
function api.can_get_resource() return true end
function api.acquire(_,id,callback)
    e.callback=callback; e.ticket={id=id}; return e.ticket
end
function api.release(ticket) assert(ticket==e.ticket); e.releases=e.releases+1 end
function get_mod(name) if name=='CustomAssets' then return api else return mod end end
Managers={package={},world={_worlds=e.worlds,_disabled_worlds={}}}
Matrix4x4={identity=function() return {} end}
local function valid(unit) assert(unit and not unit.world.dead, 'access after world teardown') end
Unit={}
function Unit.alive(unit) valid(unit); return unit.alive end
function Unit.world_pose(unit) valid(unit); return {world=unit.world} end
function Unit.get_data(unit) valid(unit); return unit.name end
function Unit.set_unit_objects_visibility(unit,value) valid(unit); unit.visible=value end
function Unit.set_unit_visibility(unit,value) valid(unit); unit.visible=value end
function Unit.set_mesh_visibility(unit) valid(unit) end
function Unit.set_local_pose(unit) valid(unit) end
function Unit.set_unit_culling(unit) valid(unit) end
function Unit.set_shader_pass_flag_for_meshes_in_unit_and_childs(unit) valid(unit); unit.fp=true end
World={LINK_MODE_NONE=0}
function World.spawn_unit_ex(world,name,_,pose)
    assert(not world.dead and pose.world==world, 'cross-world spawn')
    e.spawns=e.spawns+1
    return {world=world,name=name,alive=true,visible=true,custom=true}
end
function World.link_unit(world,unit,_,root)
    assert(root.native and unit.custom and root.world==world, 'native ownership violation')
    unit.parent=root
end
function World.destroy_unit(world,unit) assert(not world.dead); unit.alive=false end
e.target={}
local shared_options={}
function e.options(f)
    shared_options.world=f.world; shared_options.unit_spawner=f.spawner
    shared_options.is_first_person=f.fp
    return shared_options
end
function e.fixture(fp)
    local world={}; e.worlds[world]=world
    local root={world=world,name='native_root',alive=true,native=true}
    local f={world=world,root=root,map={[root]={}},original={},fp=fp,item={weapon_template='forcesword_p1_m1'}}
    f.spawner={_world=world}
    function f.spawner:spawn_unit(name,pose)
        assert(not self.destroyed, 'spawn through destroyed UI spawner')
        return World.spawn_unit_ex(self._world,name,nil,pose)
    end
    function f.spawner:mark_for_deletion(unit)
        local class=fp and 'UnitSpawnerManager' or 'UIUnitSpawner'
        e.hooks[class].mark_for_deletion(function(_,u)
            assert(not u.queued, 'double deletion'); u.queued=true; e.queued[#e.queued+1]=u
        end,self,unit)
    end
    for _,kind in ipairs({'grip','hilt','blade','pommel'}) do
        local unit={world=world,alive=true,visible=true,native=true,
            name='content/weapons/sword/attachments/'..kind..'_01/'..kind..'_01'}
        f.original[#f.original+1]=unit; f.map[root][#f.map[root]+1]=unit
    end
    return f
end
function e.spawn(f)
    return e.hooks[e.target].spawn_item(function() return f.root,f.map,'tail',nil,17 end,f.item,e.options(f))
end
function e.visual(f)
    for _,unit in ipairs(f.map[f.root]) do if unit.custom and unit.alive then return unit end end
end
function e.load() e.callback(e.ticket,{},nil); mod.update(.01) end
function e.flush()
    for _,unit in ipairs(e.queued) do unit.alive=false end
    e.queued={}; mod.update(.01)
end
