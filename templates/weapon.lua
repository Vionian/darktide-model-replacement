local mod = get_mod('__MOD_ID__')
local S = mod:io_dofile('__MOD_ID__/scripts/mods/__MOD_ID__/selection')
local WorldState = mod:io_dofile('__MOD_ID__/scripts/mods/__MOD_ID__/particle_controls')
local records, by_visual, retiring, pending = {}, {}, {}, {}
local contexts, by_native = {}, {}
local dead_spawners = setmetatable({}, {__mode = 'k'})
local deleting_native = setmetatable({}, {__mode = 'k'})
local dead_worlds = setmetatable({}, {__mode = 'k'})
local Effects, Viewmodel
local function selected(item)
    return S.profile(item)
end
local installed = setmetatable({}, {__mode = 'k'})
local api, ticket, package_manager
local ready, initialized, shutting_down = false, false, false
local generation, spawn_depth, replaced, skipped, retry = 0, 0, 0, 0, 0
local state, last_error = 'waiting', nil
mod.wmr_no_models = function() mod:echo('%s',mod:localize('no_adapted_weapons')) end
local function alive(unit) return unit ~= nil and Unit.alive(unit) end
local function pack(...) return {n = select('#', ...), ...} end
local function count(t) local n = 0; for _ in pairs(t) do n = n + 1 end; return n end
local function world_valid(world) return world ~= nil and not dead_worlds[world] and WorldState.world_registered(world) end
local function settings_valid(settings)
    if not settings or not world_valid(settings.world) or settings.in_editor then return false end
    local spawner = settings.unit_spawner
    return not spawner or (not dead_spawners[spawner] and (not spawner._world or spawner._world == settings.world))
end
local function snapshot(settings)
    -- EquipmentComponent._attach_settings and freestanding items reuse shared
    -- tables across worlds and first/third person. Never retain those tables.
    return {world=settings.world, unit_spawner=settings.unit_spawner,
        is_first_person=settings.is_first_person == true, in_editor=settings.in_editor}
end
local function forget_context(root)
    local context = contexts[root]
    if context then
        for _, unit in ipairs(context.originals) do if by_native[unit] == context then by_native[unit] = nil end end
        contexts[root] = nil
    end
    pending[root] = nil
end
local function problem(message)
    state, last_error = 'error', tostring(message)
    mod:warning('%s', last_error)
end
local function originals_visible(record, visible)
    for _, unit in ipairs(record.originals) do
        if alive(unit) then
            Unit.set_unit_objects_visibility(unit, visible, false)
            if Unit.get_data(unit, 'unit_name') and Unit.get_data(unit, 'unit_name'):match('/blade_ml01/blade_ml01$') then
                Unit.set_mesh_visibility(unit, 'fx_blade', visible)
            end
            if VisibilityContexts and VisibilityContexts.SHADOW_CASTER_CONTEXT then
                Unit.set_unit_objects_visibility(unit, visible, false, VisibilityContexts.SHADOW_CASTER_CONTEXT)
            end
            if VisibilityContexts and VisibilityContexts.RAYTRACING_CONTEXT then
                Unit.set_unit_objects_visibility(unit, visible and not record.first_person, false, VisibilityContexts.RAYTRACING_CONTEXT)
            end
        end
    end
end
local function appearance(record) end
local function retire(record, restore)
    if Effects then Effects.retire(record) end
    records[record.root] = nil
    local children = record.map and record.map[record.root]
    if children then
        for i = #children, 1, -1 do
            if children[i] == record.visual then table.remove(children, i) end
        end
    end
    if record.map then record.map[record.visual] = nil end
    if not world_valid(record.world) then
        retiring[record.visual], by_visual[record.visual] = nil, nil
        return
    end
    if restore then originals_visible(record, true) end
    if alive(record.visual) then
        Unit.set_unit_visibility(record.visual, false, true)
        retiring[record.visual] = record
        if not record.deleting then
            record.deleting = true
            if record.spawner and not dead_spawners[record.spawner] then record.spawner:mark_for_deletion(record.visual)
            else World.destroy_unit(record.world, record.visual) end
        end
    else
        by_visual[record.visual] = nil
    end
end
local function clear(restore, keep_pending)
    local list = {}
    for _, record in pairs(records) do list[#list + 1] = record end
    for _, record in ipairs(list) do
        if keep_pending then pending[record.root] = record end
        retire(record, restore)
    end
end
local function prune()
    for root, context in pairs(contexts) do
        if not settings_valid(context.settings) or not alive(root) then
            if records[root] then retire(records[root], false) end
            forget_context(root)
        end
    end
    for unit, record in pairs(retiring) do
        if not world_valid(record.world) or not alive(unit) then retiring[unit], by_visual[unit] = nil, nil end
    end
end
local function release_if_unused()
    prune()
    if ticket and not next(records) and not next(retiring) and (not Effects or Effects.unused()) then
        api.release(ticket)
        ticket, ready = nil, false
    end
end
local function acquire()
    if not initialized or not mod:is_enabled() or shutting_down or ticket then return end
    if not Managers or not Managers.package then state = 'waiting'; return end
    api = get_mod('CustomAssets')
    if not api or type(api.is_api_compatible) ~= 'function' or not api.is_api_compatible(1) then
        problem('Custom Assets API v1 is unavailable.'); return
    end
    generation = generation + 1
    local request_generation = generation
    package_manager, state = Managers.package, 'loading'
    local result, err = api.acquire(mod, S.asset, function(loaded, asset, load_error)
        if generation ~= request_generation or shutting_down or not mod:is_enabled() then return end
        if load_error then ticket = nil; problem(load_error); return end
        local units_ok=api.can_get_resource('unit','content/mods/__ASSET_ID__/weapon')
        if not asset or not units_ok or (Effects and not Effects.resources_available(api)) then
            api.release(loaded); ticket = nil
            problem('Replacement unit is unavailable; refresh the Custom Assets registration.'); return
        end
        ready, state, last_error = true, 'ready', nil
        mod:info('%s', 'Weapon resources ready: Replacement model.')
    end, {reference_name = '__MOD_ID__:visuals', prioritize = true})
    ticket = result
    if not result then problem(err or 'Asset acquisition failed.') end
end
local function attach(item, settings, root, map)
    if not mod:is_enabled() or not settings_valid(settings)
        or not map or not map[root] then return end
    if deleting_native[root] or not alive(root) then forget_context(root); return end
    local family = S.family(item)
    if not family then return end
    settings = snapshot(settings)
    local originals, kinds, grip, blade = {}, {}, false, false
    for _, unit in ipairs(map[root]) do
        if deleting_native[unit] then
            if records[root] then retire(records[root], false) end
            forget_context(root); return
        end
        if alive(unit) then
            local kind = S.part_kind(Unit.get_data(unit, 'unit_name'))
            if kind then
                originals[#originals + 1], kinds[unit] = unit, kind
                grip, blade = grip or kind == 'grip', blade or kind == 'blade'
            end
        end
    end
    if not grip or not blade then
        if records[root] then retire(records[root], true) end
        forget_context(root)
        skipped = skipped + 1; return
    end
    forget_context(root)
    local context = {item=item, settings=settings, world=settings.world, spawner=settings.unit_spawner,
        root=root, map=map, originals=originals, setting=family.setting}
    contexts[root] = context
    for _, unit in ipairs(originals) do by_native[unit] = context end
    local profile = selected(item)
    if not profile then
        if records[root] then retire(records[root], true) end
        return
    end
    if not ready then pending[root] = context; return end
    local old = records[root]
    if old then
        local same = old.map == map and old.profile == profile and old.world == settings.world
            and old.spawner == settings.unit_spawner and old.first_person == settings.is_first_person
            and alive(old.visual) and not old.deleting and #old.originals == #originals
        for _, unit in ipairs(originals) do same = same and old.kinds[unit] == kinds[unit] end
        if same then originals_visible(old, false); return end
        retire(old, true)
    end
    local record = {item=item, profile=profile, settings=settings, root=root, map=map, originals=originals, kinds=kinds,
        world=settings.world, spawner=settings.unit_spawner, first_person=settings.is_first_person == true}
    local ok, err = pcall(function()
        local pose = Unit.world_pose(root, 1)
        if record.spawner then record.visual = record.spawner:spawn_unit(profile.unit, pose)
        else record.visual = World.spawn_unit_ex(record.world, profile.unit, nil, pose) end
        if not alive(record.visual) then error('Weapon visual spawn returned no unit.') end
        -- Follow the native equipment root. Never reparent player hands or gameplay equipment.
        World.link_unit(record.world, record.visual, 1, root, 1, World.LINK_MODE_NONE)
        Unit.set_local_pose(record.visual, 1, Matrix4x4.identity())
        if record.first_person then
            Unit.set_unit_culling(record.visual, false)
            Unit.set_shader_pass_flag_for_meshes_in_unit_and_childs(record.visual, 'custom_fov', true)
            if VisibilityContexts and VisibilityContexts.RAYTRACING_CONTEXT then
                Unit.set_unit_objects_visibility(record.visual, false, true, VisibilityContexts.RAYTRACING_CONTEXT)
            end
        end
        map[root][#map[root] + 1], map[record.visual] = record.visual, {}
        records[root], by_visual[record.visual] = record, record
        if profile.cover then
            for _, channel in ipairs({'r','g','b'}) do
                Unit.set_mesh_visibility(record.visual,'cover_'..channel..'_mesh_p0',false)
                Unit.set_mesh_visibility(record.visual,'cover_'..channel..'_mesh_p0_back',false)
            end
        end
        appearance(record)
        originals_visible(record, false)
    end)
    if not ok then
        if record.visual then retire(record, true) end
        problem(err); return
    end
    replaced = replaced + 1
end
local function install(target)
    if installed[target] then return end
    installed[target] = true
    mod:hook(target, 'spawn_item', function(func, item, settings, ...)
        local own_settings = settings and snapshot(settings)
        spawn_depth = spawn_depth + 1
        local result = pack(pcall(func, item, settings, ...))
        spawn_depth = spawn_depth - 1
        if not result[1] then error(result[2], 0) end
        attach(item, own_settings, result[2], result[3])
        return unpack(result, 2, result.n)
    end)
    mod:hook(target, 'spawn_item_attachments', function(func, item, overrides, settings, root, ...)
        local own_settings = settings and snapshot(settings)
        local result = pack(func(item, overrides, settings, root, ...))
        if spawn_depth == 0 then attach(item, own_settings, root, result[1]) end
        return unpack(result, 1, result.n)
    end)
end
for _, class in ipairs({'UnitSpawnerManager', 'UIUnitSpawner'}) do
    mod:hook(class, 'mark_for_deletion', function(func, self, unit, ...)
        deleting_native[unit] = true
        local context = contexts[unit] or by_native[unit]
        if context then
            forget_context(context.root)
            if records[context.root] then retire(records[context.root], false) end
        end
        if by_visual[unit] then by_visual[unit].deleting = true end
        return func(self, unit, ...)
    end)
end
mod:hook('UIUnitSpawner', 'destroy', function(func, self, ...)
    -- Invalidate before the original teardown and any reentrant callbacks.
    dead_spawners[self] = true
    local list = {}
    for root, context in pairs(contexts) do if context.spawner == self then list[#list+1] = root end end
    for _, root in ipairs(list) do
        forget_context(root)
        if records[root] then retire(records[root], false) end
    end
    return func(self, ...)
end)
mod:hook('WorldManager', 'destroy_world', function(func, self, world, ...)
    if not self.locked then
        local resolved = type(world) == 'string' and self:world(world) or world
        dead_worlds[resolved] = true
        if Effects then Effects.forget_world(resolved) end
        if Viewmodel then Viewmodel.forget_world(resolved) end
        for root, record in pairs(records) do
            if record.world == resolved then records[root], by_visual[record.visual] = nil, nil end
        end
        for unit, record in pairs(retiring) do
            if record.world == resolved then retiring[unit], by_visual[unit] = nil, nil end
        end
        for root, record in pairs(pending) do
            if record.settings.world == resolved then pending[root] = nil end
        end
        local list = {}
        for root, context in pairs(contexts) do if context.world == resolved then list[#list+1] = root end end
        for _, root in ipairs(list) do forget_context(root) end
    end
    return func(self, world, ...)
end)
mod.on_all_mods_loaded = function()
    initialized = true
    mod:hook_require('scripts/extension_systems/visual_loadout/utilities/visual_loadout_customization', install)
    acquire()
end
mod.on_enabled = function()
    if initialized then
        state = ready and 'ready' or 'waiting'
        if not ready then release_if_unused(); acquire() end
    end
end
mod.on_disabled = function()
    if Effects then Effects.disable() end
    if Viewmodel then Viewmodel.restore() end
    generation, state = generation + 1, 'disabled'
    mod:hook_enable('WorldManager', 'destroy_world')
    mod:hook_enable('UIUnitSpawner', 'destroy')
    mod:hook_enable('UIUnitSpawner', 'mark_for_deletion')
    mod:hook_enable('UnitSpawnerManager', 'mark_for_deletion')
    clear(true, true)
    release_if_unused()
end
mod.update = function(dt)
    if shutting_down then return end
    if Effects then Effects.update(dt) end
    prune()
    if not mod:is_enabled() then release_if_unused(); return end
    if package_manager and package_manager ~= Managers.package then
        generation = generation + 1
        clear(true, false); pending = {}
        release_if_unused()
        ready, state, package_manager = false, 'waiting', Managers.package
    end
    for root, record in pairs(records) do
        if not alive(root) or not alive(record.visual) or record.deleting then retire(record, alive(root))
        else originals_visible(record, false); appearance(record) end
    end
    if ready then
        local list = {}
        for _, record in pairs(pending) do list[#list+1] = record end
        for _, record in ipairs(list) do attach(record.item, record.settings, record.root, record.map) end
    end
    retry = retry + dt
    if retry >= 1 then
        retry = 0
        if state == 'waiting' then release_if_unused(); acquire() end
    end
end
mod.on_setting_changed = function(setting)
    if setting == 'skin_model' then
        if Viewmodel then Viewmodel.restore() end
        prune()
        local refreshed = 0
        for root, context in pairs(contexts) do
            if context.setting == setting then
                refreshed = refreshed + 1
                pending[root] = context
                if records[root] then retire(records[root], true) end
            end
        end
        mod:info('Skin refresh %s: %d live equipment context(s).', setting, refreshed)
    end
    if (setting == 'fp_height_cm' or setting == 'fp_height_zealot_cm') and Viewmodel then Viewmodel.restore() end
    if Effects then Effects.settings_changed() end
    if mod:is_enabled() then
        for _, record in pairs(records) do if alive(record.visual) then appearance(record) end end
    end
end
mod.on_unload = function(exiting)
    if Viewmodel and not exiting then Viewmodel.restore() end
    if Effects then Effects.disable() end
    shutting_down, generation = true, generation + 1
    if not exiting then clear(true, false) end
    -- The shared API retains live tickets across reload until native unit deletion/level exit.
end
mod:command('__MOD_ID___status', mod:localize('status_help'), function()
    mod:echo('%s', mod:localize('status_line', state, count(records), replaced, skipped, count(pending)))
    if last_error then mod:echo('%s', last_error) end
    mod:echo('%s', mod:localize('refresh_hint'))
end)
Viewmodel = mod:io_dofile('__MOD_ID__/scripts/mods/__MOD_ID__/viewmodel').install(mod,
    function(root) return records[root] ~= nil end)
