-- Executes the production runtime with strict native-object lifetime checks.
-- arg[1] is the actual package directory, including installed packages.
local package_root = assert(arg[1], 'pass the WeaponModelReplacement package directory')
local path = package_root .. '/scripts/mods/WeaponModelReplacement/'
local source_path = '<CHARACTER_WORKSPACE>/tools/model-work/distribution_fix/source_reference/repository/scripts/extension_systems/visual_loadout/equipment_component.lua'
local file = assert(io.open(source_path, 'rb'))
local source = file:read('*a'); file:close()
local native_block = assert(source:match('(local _attach_settings = {}.-)EquipmentComponent%._fill_attach_settings_companion'))
table.clear = table.clear or function(t) for key in pairs(t) do t[key] = nil end end
local total = 0
local function environment(loaded)
    local e = {hooks={}, settings={skin_psyker_forcesword_1h='langzhifei', skin_psyker_forcesword_2h='khravengger',
        skin_zealot_relicsword_2h='khravengger'}, spawn_count=0, faults=0, worlds={}, queued={}, enabled=true}
    local mod = {}; e.mod = mod
    function mod:get(key) return e.settings[key] end
    function mod:set(key, value) e.settings[key] = value end
    function mod:is_enabled() return e.enabled end
    function mod:localize(key, ...) return key end
    function mod:info(...) end
    function mod:warning(...) end
    function mod:echo(...) end
    function mod:command(...) end
    function mod:hook(target, name, fn)
        e.hooks[target] = e.hooks[target] or {}
        assert(not e.hooks[target][name]); e.hooks[target][name] = fn
    end
    function mod:hook_safe(target, name, fn)
        self:hook(target, name, function(original, owner, ...)
            local result = original(owner, ...); fn(owner, ...); return result
        end)
    end
    function mod:hook_enable(target, name)
        e.keep = e.keep or {}; e.keep[target .. ':' .. name] = true
    end
    function mod:hook_require(name, fn) e.install = fn end
    function mod:io_dofile(name)
        local short = name:match('/([^/]+)$')
        if short == 'ice_effects' then
            return {install=function() return {update=function() end, retire=function() end,
                forget_world=function() end, disable=function() end, unused=function() return true end,
                resources_available=function() return true end, settings_changed=function() end} end}
        elseif short == 'viewmodel' then
            return {install=function() return {restore=function() end, forget_world=function() end} end}
        elseif short == 'menu_order' then return {install=function() end} end
        return dofile(path .. short .. '.lua')
    end
    local api = {is_api_compatible=function() return true end, can_get_resource=function() return true end,
        acquire=function(_, _, callback) e.callback=callback; e.ticket={}; return e.ticket end,
        release=function() end}
    function get_mod(name) if name == 'CustomAssets' then return api end; return mod end
    Managers = {package={}, world={_worlds=e.worlds, _disabled_worlds={}}}
    VisibilityContexts = nil
    Matrix4x4 = {identity=function() return {identity=true} end}
    function Vector3(x,y,z) return {x,y,z} end
    local function valid(world)
        if not world or world.dead then e.faults=e.faults+1; error('native access to destroyed world') end
    end
    Unit = {
        alive=function(unit) valid(unit.world); return unit.alive end,
        get_data=function(unit) valid(unit.world); return unit.name end,
        world_pose=function(unit) valid(unit.world); return {world=unit.world} end,
        set_unit_objects_visibility=function(unit, visible) valid(unit.world); unit.visible=visible end,
        set_mesh_visibility=function(unit, _, visible) valid(unit.world); unit.fx=visible end,
        set_unit_visibility=function(unit, visible) valid(unit.world); unit.visible=visible end,
        set_scalar_for_material=function(unit) valid(unit.world) end,
        set_vector3_for_material=function(unit) valid(unit.world) end,
        set_local_pose=function(unit) valid(unit.world) end,
        set_unit_culling=function(unit) valid(unit.world) end,
        set_shader_pass_flag_for_meshes_in_unit_and_childs=function(unit) valid(unit.world); unit.fp=true end,
    }
    World = {LINK_MODE_NONE=0}
    function World.spawn_unit_ex(world, name, _, pose)
        valid(world)
        if pose.world ~= world then e.faults=e.faults+1; error('native weapon crossed worlds') end
        e.spawn_count=e.spawn_count+1
        return {world=world, name=name, alive=true, visible=true}
    end
    function World.link_unit(world, visual, _, root)
        valid(world); assert(root.world==world and visual.world==world); visual.parent=root
    end
    function World.destroy_unit(world, unit) valid(world); unit.alive=false end
    function e.dispatch(class, name, original, owner, ...)
        local hook=e.hooks[class] and e.hooks[class][name]
        if hook then return hook(original, owner, ...) end
        return original(owner, ...)
    end
    local attach_settings=assert(loadstring('local EquipmentComponent = {}\n' .. native_block .. '\nreturn EquipmentComponent._attach_settings'))()
    e.native_settings=attach_settings
    function e.fixture(template, fp, world)
        world=world or {}; e.worlds[world]=world
        local class=fp and 'UnitSpawnerManager' or 'UIUnitSpawner'
        local spawner={_world=world}
        function spawner:spawn_unit(name, pose)
            assert(not self.destroyed, 'using a destroyed UIUnitSpawner')
            return World.spawn_unit_ex(self._world, name, nil, pose)
        end
        function spawner:mark_for_deletion(unit)
            return e.dispatch(class, 'mark_for_deletion', function(_, u)
                assert(not u.queued, 'double native deletion'); u.queued=true; e.queued[#e.queued+1]=u
            end, self, unit)
        end
        local prefix=template:match('^powersword_2h') and '2h_power_sword' or template:match('^forcesword_2h') and '2h_force_sword' or 'force_sword'
        local root={world=world, alive=true, name='native_root'}
        local map={[root]={}}
        for _, part in ipairs({'grip_01','hilt_01','blade_01','pommel_01'}) do
            map[root][#map[root]+1]={world=world,alive=true,visible=true,name='content/weapons/player/melee/'..prefix..'/attachments/'..part..'/'..part}
        end
        local f={world=world,root=root,map=map,spawner=spawner,fp=fp,item={weapon_template=template},class=class}
        function f.options()
            local options=attach_settings({_world=world,_unit_spawner=spawner})
            options.is_first_person=fp; return options
        end
        return f
    end
    e.target={}
    function e.spawn(f, options)
        return e.hooks[e.target].spawn_item(function() return f.root,f.map,'tail',nil,17 end, f.item, options or f.options())
    end
    function e.visual(f)
        for _, unit in ipairs(f.map[f.root]) do
            if unit.alive and unit.name:match('content/mods/weapon_model_replacement/') then return unit end
        end
    end
    function e.setting(name, value)
        e.settings[name]=value; mod.on_setting_changed(name); mod.update(.01)
    end
    function e.load() e.callback(e.ticket, {}, nil); mod.update(.01) end
    function e.flush()
        for _, unit in ipairs(e.queued) do unit.alive=false end
        e.queued={}; mod.update(.01)
    end
    function e.destroy_world(world, direct)
        local function original(_, target)
            assert(target==world); e.worlds[world]=nil; Managers.world._disabled_worlds[world]=nil; world.dead=true
        end
        if direct then original(nil,world)
        else e.dispatch('WorldManager','destroy_world', original, {}, world) end
    end
    dofile(path .. 'WeaponModelReplacement.lua')
    mod.on_all_mods_loaded(); e.install(e.target)
    if loaded ~= false then e.load() end
    return e
end
local function check(name, fn)
    local e=environment(); fn(e); assert(e.faults==0, 'unsafe native access was swallowed by pcall')
    total=total+1; print('PASS '..name)
end
check('native EquipmentComponent reuses and clears one shared settings table', function(e)
    local a=e.fixture('forcesword_p1_m1',true); local b=e.fixture('forcesword_2h_p1_m1',false)
    local shared=a.options(); shared.marker=true
    assert(b.options()==shared and shared.world==b.world and shared.marker==nil)
end)
check('active weapon refresh preserves its world after shared settings reuse', function(e)
    local a=e.fixture('forcesword_p1_m1',true); e.spawn(a)
    local unrelated=e.fixture('forcesword_2h_p1_m1',false); unrelated.options()
    e.setting('skin_psyker_forcesword_1h','langzhifei')
    assert(e.visual(a) and e.visual(a).world==a.world and e.visual(a).fp)
end)
check('active weapon refresh ignores a destroyed last-used preview world', function(e)
    local a=e.fixture('forcesword_2h_p1_m1',true); e.spawn(a)
    local temporary=e.fixture('forcesword_p1_m1',false); temporary.options(); e.destroy_world(temporary.world,true)
    e.setting('skin_psyker_forcesword_2h','khravengger')
    assert(e.visual(a) and e.visual(a).world==a.world)
end)
check('first and third person keep independent flags with one shared table', function(e)
    local world={}; local a=e.fixture('forcesword_p1_m1',true,world); e.spawn(a)
    local b=e.fixture('forcesword_p1_m1',false,world); e.spawn(b)
    e.setting('skin_psyker_forcesword_1h','langzhifei')
    assert(e.visual(a).fp and not e.visual(b).fp)
end)
for _, template in ipairs({'forcesword_p1_m1','forcesword_p1_m2','forcesword_p1_m3'}) do
    check(template..' selects Langzhifei on an existing original sword', function(e)
        e.settings.skin_psyker_forcesword_1h='none'
        local a=e.fixture(template,true); e.spawn(a); assert(not e.visual(a))
        e.setting('skin_psyker_forcesword_1h','langzhifei')
        assert(e.visual(a).name:match('/langzhifei$'))
    end)
end
check('Langzhifei dropdown leaves both Khravengger families untouched', function(e)
    local a=e.fixture('forcesword_2h_p1_m1',false); local b=e.fixture('powersword_2h_p1_m1',false)
    e.spawn(a); e.spawn(b); local av,bv,n=e.visual(a),e.visual(b),e.spawn_count
    e.setting('skin_psyker_forcesword_1h','none'); e.setting('skin_psyker_forcesword_1h','langzhifei')
    assert(e.visual(a)==av and e.visual(b)==bv and e.spawn_count==n)
end)
check('forty repeated dropdown cycles preserve exactly one visual', function(e)
    local a=e.fixture('forcesword_p1_m1',true); e.spawn(a)
    for _=1,40 do
        e.setting('skin_psyker_forcesword_1h','none'); assert(not e.visual(a) and a.map[a.root][1].visible)
        e.flush(); e.setting('skin_psyker_forcesword_1h','langzhifei'); assert(e.visual(a)); e.flush()
        assert(#a.map[a.root]==5)
    end
end)
check('destroyed UI spawner cannot be reentered during its teardown', function(e)
    local a=e.fixture('forcesword_p1_m1',false); e.spawn(a)
    e.dispatch('UIUnitSpawner','destroy',function(owner)
        e.spawn(a); owner.destroyed=true; return 'destroy-tail'
    end,a.spawner)
    local n=e.spawn_count; e.setting('skin_psyker_forcesword_1h','langzhifei'); assert(e.spawn_count==n and not e.visual(a))
end)
check('queued native root cancels dropdown rebuild before engine deletion', function(e)
    local a=e.fixture('forcesword_p1_m1',false); e.spawn(a)
    a.spawner:mark_for_deletion(a.root); local n=e.spawn_count
    e.setting('skin_psyker_forcesword_1h','langzhifei'); assert(e.spawn_count==n and not e.visual(a)); e.flush()
end)
check('queued native blade invalidates retained-root attachment context', function(e)
    local a=e.fixture('forcesword_p1_m1',false); e.spawn(a)
    a.spawner:mark_for_deletion(a.map[a.root][3]); local n=e.spawn_count
    e.setting('skin_psyker_forcesword_1h','langzhifei'); assert(e.spawn_count==n); e.flush()
end)
check('mismatched native spawner world never receives a spawn', function(e)
    local a=e.fixture('forcesword_p1_m1',false); a.spawner._world={}
    e.spawn(a); assert(e.spawn_count==0 and not e.visual(a))
end)
check('world disappearance is pruned before even Unit.alive is called', function(e)
    local a=e.fixture('forcesword_p1_m1',false); e.spawn(a); e.destroy_world(a.world,true)
    e.mod.update(.01); e.setting('skin_psyker_forcesword_1h','langzhifei')
end)
check('WorldManager destruction forgets pending and active contexts', function(e)
    local a=e.fixture('forcesword_p1_m1',false); e.spawn(a); e.destroy_world(a.world)
    e.mod.update(.01); e.setting('skin_psyker_forcesword_1h','langzhifei')
end)
check('world destruction while disabled cannot resurrect stale equipment', function(e)
    local a=e.fixture('forcesword_p1_m1',false); e.spawn(a)
    e.enabled=false; e.mod.on_disabled()
    assert(e.keep['UIUnitSpawner:destroy'] and e.keep['UIUnitSpawner:mark_for_deletion'])
    e.destroy_world(a.world); e.mod.update(.01)
    e.enabled=true; e.mod.on_enabled(); e.load(); assert(e.spawn_count==1)
end)
check('temporarily disabled registered worlds remain valid previews', function(e)
    local a=e.fixture('forcesword_p1_m1',false)
    e.worlds[a.world]=nil; Managers.world._disabled_worlds[a.world]=a.world
    e.spawn(a); assert(e.visual(a))
end)
check('native return tuple including nil gaps is preserved', function(e)
    local a=e.fixture('forcesword_p1_m1',false)
    local root,map,tail,gap,last=e.spawn(a)
    assert(root==a.root and map==a.map and tail=='tail' and gap==nil and last==17)
end)
check('loading queue keeps original world despite destroyed shared-table owner', function()
    local e=environment(false)
    local a=e.fixture('forcesword_p1_m1',true); e.spawn(a)
    local temporary=e.fixture('forcesword_2h_p1_m1',false); temporary.options(); e.destroy_world(temporary.world,true)
    e.load(); assert(e.visual(a) and e.visual(a).fp and e.faults==0)
end)
check('loading queue is cancelled by UI spawner destruction', function()
    local e=environment(false); local a=e.fixture('forcesword_p1_m1',false); e.spawn(a)
    e.dispatch('UIUnitSpawner','destroy',function(owner) owner.destroyed=true end,a.spawner)
    e.load(); assert(e.spawn_count==0 and e.faults==0)
end)
check('loading queue is cancelled by native root deletion', function()
    local e=environment(false); local a=e.fixture('forcesword_p1_m1',false); e.spawn(a)
    a.spawner:mark_for_deletion(a.root); e.load(); assert(e.spawn_count==0 and e.faults==0)
end)
check('spawn hook snapshots options before reentrant native callbacks', function(e)
    local a=e.fixture('forcesword_p1_m1',true); local temporary=e.fixture('forcesword_2h_p1_m1',false)
    e.hooks[e.target].spawn_item(function()
        temporary.options(); e.destroy_world(temporary.world,true); return a.root,a.map
    end,a.item,a.options())
    assert(e.visual(a) and e.visual(a).fp)
end)
check('attachment-only hook snapshots options before native callbacks', function(e)
    local a=e.fixture('forcesword_p1_m1',true); local temporary=e.fixture('forcesword_2h_p1_m1',false)
    e.hooks[e.target].spawn_item_attachments(function()
        temporary.options(); e.destroy_world(temporary.world,true); return a.map
    end,a.item,{},a.options(),a.root)
    assert(e.visual(a) and e.visual(a).fp)
end)
check('native root cleanup callback cannot resurrect queued equipment', function(e)
    local a=e.fixture('forcesword_p1_m1',false); e.spawn(a)
    local n=e.spawn_count
    e.dispatch('UIUnitSpawner','mark_for_deletion',function() e.spawn(a) end,a.spawner,a.root)
    e.mod.update(.01); assert(e.spawn_count==n and not e.visual(a))
end)
check('world teardown callback cannot recreate a doomed preview', function(e)
    local a=e.fixture('forcesword_p1_m1',false); e.spawn(a); local n=e.spawn_count
    e.dispatch('WorldManager','destroy_world',function()
        e.spawn(a); e.worlds[a.world]=nil; a.world.dead=true
    end,{},a.world)
    e.mod.update(.01); assert(e.spawn_count==n)
end)
print('PREVIEW_LIFECYCLE_TESTS_OK '..total)
