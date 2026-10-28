-- Cosmetic replacement only. Native equipment and driver bones remain game-owned.
local mod = get_mod('__MOD_ID__')
local tracked, records, retiring = {}, {}, {}
local dead_worlds = setmetatable({}, {__mode='k'})
local tickets, loaded, api = {}, {}, nil
local generation, initialized, stopped = 0, false, false
local body_resource = 'content/mods/__ASSET_ID__/body'
local arms_resource = 'content/mods/__ASSET_ID__/arms'
local function alive(unit) return unit ~= nil and Unit.alive(unit) end
local function world_valid(world) return world ~= nil and not dead_worlds[world] end
local function hide_slots(ext, key)
    local attachments_key = key=='unit_1p' and 'attachments_by_unit_1p' or 'attachments_by_unit_3p'
    for name, slot in pairs(ext._equipment or {}) do
        if name:match('^slot_body_') or name:match('^slot_gear_') then
            local unit = slot[key]
            if alive(unit) then
                Unit.set_unit_visibility(unit, false, true)
                for _, child in ipairs(slot[attachments_key] and slot[attachments_key][unit] or {}) do
                    if alive(child) then Unit.set_unit_visibility(child, false, true) end
                end
            end
        end
    end
end
local function delete_visual(record, field)
    local unit = record[field]
    record[field] = nil
    if alive(unit) and world_valid(record.world) then
        Unit.set_unit_visibility(unit, false, true)
        record.spawner:mark_for_deletion(unit)
        retiring[unit] = record.world
    end
end
local function clear(ext, restore)
    local record = records[ext]
    records[ext] = nil
    if record then
        delete_visual(record, 'body')
        delete_visual(record, 'arms')
    end
    if restore and alive(ext._unit) and ext.force_update_item_visibility then
        ext:force_update_item_visibility()
    end
end
local function target(ext)
    if not ext.__public_breed or (ext.__public_breed ~= 'human' and ext.__public_breed ~= 'cryptic') then return false end
    local wanted = mod:get('target_class') or 'all'
    return ext._player ~= nil and (wanted == 'all' or wanted == ext.__public_archetype)
end
local function spawn(record, parent, resource, first_person)
    if not alive(parent) then return nil end
    local unit = record.spawner:spawn_unit(resource, Unit.world_pose(parent, 1))
    if not alive(unit) then return nil end
    World.link_unit(record.world, unit, 1, parent, 1, World.LINK_MODE_NODE_NAME)
    Unit.set_unit_culling(unit, false)
    if first_person then Unit.set_shader_pass_flag_for_meshes_in_unit_and_childs(unit, 'custom_fov', true) end
    return unit
end
local function apply(ext)
    if stopped or not mod:is_enabled() or not target(ext) or not loaded.body or not loaded.arms then return end
    local world = ext.__public_world
    local spawner = Managers.state and Managers.state.unit_spawner
    if not world_valid(world) or not spawner or not alive(ext._unit) then return end
    local record = records[ext]
    if record and (record.world ~= world or record.parent ~= ext._unit or record.spawner ~= spawner) then
        clear(ext, false)
        record = nil
    end
    if not record then
        record = {world=world, parent=ext._unit, spawner=spawner}
        records[ext] = record
    end
    if not alive(record.body) then record.body = spawn(record, ext._unit, body_resource, false) end
    local first_person = ext.__public_first_person == true
    if first_person and mod:get('first_person_arms') ~= false then
        if not alive(record.arms) then record.arms = spawn(record, ext._first_person_unit, arms_resource, true) end
    elseif record.arms then
        delete_visual(record, 'arms')
    end
    if alive(record.body) then
        Unit.set_unit_visibility(record.body, not first_person, true)
        if not first_person then hide_slots(ext, 'unit_3p') end
    end
    if alive(record.arms) then
        Unit.set_unit_visibility(record.arms, first_person, true)
        if first_person then hide_slots(ext, 'unit_1p') end
    end
end
local function acquire()
    if stopped or not initialized or not mod:is_enabled() then return end
    api = get_mod('CustomAssets')
    if not api or not api.is_api_compatible(1) then return end
    local epoch = generation
    for _, suffix in ipairs({'body','arms'}) do
        if not tickets[suffix] then
            local kind = suffix
            local ticket, err = api.acquire(mod, '__MOD_ID__:__ASSET_ID___'..kind, function(ticket, asset, error)
                if epoch ~= generation or stopped or not mod:is_enabled() then
                    api.release(ticket)
                    if tickets[kind] == ticket then tickets[kind] = nil end
                    return
                end
                if error or not asset then
                    tickets[kind], loaded[kind] = nil, nil
                    mod:error('%s', tostring(error or 'Missing asset'))
                    return
                end
                loaded[kind] = true
            end)
            tickets[kind] = ticket
            if err then mod:error('%s', tostring(err)) end
        end
    end
end
for _, class in ipairs({'PlayerUnitVisualLoadoutExtension','PlayerHuskVisualLoadoutExtension'}) do
    mod:hook_safe(class, 'init', function(self, context, unit, data)
        self.__public_world = context and context.world
        local archetype = data and data.archetype
        self.__public_breed = archetype and archetype.breed
        self.__public_archetype = archetype and archetype.name
        tracked[self] = true
    end)
    mod:hook_safe(class, '_update_item_visibility', function(self, first_person)
        self.__public_first_person = first_person == true
        apply(self)
    end)
    mod:hook(class, 'destroy', function(original, self, ...)
        tracked[self] = nil
        clear(self, false)
        return original(self, ...)
    end)
end
mod:hook('WorldManager', 'destroy_world', function(original, self, world, ...)
    if not self.locked then
        local resolved = type(world)=='string' and self:world(world) or world
        dead_worlds[resolved] = true
        for ext, record in pairs(records) do
            if record.world == resolved then records[ext], tracked[ext] = nil, nil end
        end
        for unit, owner in pairs(retiring) do if owner == resolved then retiring[unit] = nil end end
    end
    return original(self, world, ...)
end)
mod.on_all_mods_loaded = function() initialized = true; acquire() end
mod.on_enabled = function() acquire() end
mod.on_disabled = function()
    generation = generation + 1
    for ext in pairs(records) do clear(ext, true) end
    mod:hook_enable('WorldManager', 'destroy_world')
    for _, class in ipairs({'PlayerUnitVisualLoadoutExtension','PlayerHuskVisualLoadoutExtension'}) do mod:hook_enable(class, 'destroy') end
end
mod.on_setting_changed = function()
    for ext in pairs(records) do clear(ext, true) end
end
mod.update = function()
    for unit, world in pairs(retiring) do
        if not world_valid(world) or not alive(unit) then retiring[unit] = nil end
    end
    if not mod:is_enabled() then
        if not next(records) and not next(retiring) and api then
            for _, ticket in pairs(tickets) do api.release(ticket) end
            tickets, loaded = {}, {}
        end
        return
    end
    acquire()
    for ext in pairs(tracked) do
        if not alive(ext._unit) then tracked[ext] = nil; clear(ext, false)
        elseif not target(ext) then clear(ext, false)
        else apply(ext) end
    end
end
mod.on_unload = function(exiting)
    stopped, generation = true, generation + 1
    if not exiting then for ext in pairs(records) do clear(ext, true) end end
    -- Deletions are deferred. The shared API keeps live owner tickets until level teardown.
end
