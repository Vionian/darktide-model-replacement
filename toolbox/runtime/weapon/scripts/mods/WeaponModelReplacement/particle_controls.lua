local P = {}
local materials, warned = {}, {}
local now, succeeded, waiting, failed = 0, 0, 0, 0
local RETRY_INTERVAL, RETRY_WINDOW, MAX_ATTEMPTS = .1, 1, 11
-- Both parameters are confirmed vector3 fields in the compiled GPU draw material.
local GPU_VECTOR3 = {material_variable_8b0f8e84 = true, material_variable_8b0f8e84_118d5a82 = true}

function P.world_registered(world)
    local manager = Managers and Managers.world
    if not manager then return false end
    for _, candidate in pairs(manager._worlds or {}) do if candidate == world then return true end end
    for _, candidate in pairs(manager._disabled_worlds or {}) do if candidate == world then return true end end
    return false
end

function P.forget(world, id)
    local ids = materials[world]
    if not ids then return end
    local function remove(record)
        for _, request in pairs(record.bindings) do
            if request.status == "waiting" then waiting = waiting - 1 end
        end
    end
    if id ~= nil then
        if ids[id] then remove(ids[id]); ids[id] = nil end
        if not next(ids) then materials[world] = nil end
    else
        for _, record in pairs(ids) do remove(record) end
        materials[world] = nil
    end
end

function P.clear()
    materials, waiting = {}, 0
end

function P.status()
    return succeeded, waiting, failed
end

local function attempt(world, id, request)
    request.attempts = request.attempts + 1
    local binding, cloud, material = request.binding
    -- Mesh/vector4 writes remain forbidden even with stale manifest data.
    if binding.vector4 or binding.kind == "mesh" then return false end
    if binding.kind == "gpu" then
        if not World.get_particles_material or not Material or not Material.set_vector3 then return false end
        for _, parameter in ipairs(binding.colors) do
            if not GPU_VECTOR3[parameter[1]] then return false end
        end
        -- The native wizard FX get GPU material instances directly. Our manifest
        -- supplies confirmed render keys; never try emit/sim as a fallback.
        for _, candidate in ipairs(binding.clouds or {}) do
            material = World.get_particles_material(world, id, candidate)
            if material then break end
        end
        if not material then return false end
    elseif World.has_particles_material then
        for _, candidate in ipairs(binding.clouds or {binding.cloud}) do
            if World.has_particles_material(world, id, candidate) then cloud = candidate; break end
        end
    end
    if not cloud and not material then return false end
    for _, parameter in ipairs(binding.colors) do
        local factor = parameter[2] * request.strength
        local value = Vector3(request.r * factor, request.g * factor, request.b * factor)
        if material then
            Material.set_vector3(material, parameter[1], value)
        else
            World.set_particles_material_vector3(world, id, cloud, parameter[1], value)
        end
    end
    if request.status == "waiting" then waiting = waiting - 1 end
    if request.status ~= "ready" then succeeded = succeeded + 1 end
    request.status = "ready"
    return true
end

local function apply_material(world, id, name, binding, index, r, g, b, strength)
    local ids = materials[world]
    if not ids then ids = {}; materials[world] = ids end
    local record = ids[id]
    if record and record.name ~= name then P.forget(world, id); ids = materials[world] or {}; materials[world] = ids; record = nil end
    if not record then record = {name = name, bindings = {}}; ids[id] = record end
    local request = record.bindings[index]
    if not request then
        request = {binding = binding, attempts = 0, deadline = now + RETRY_WINDOW, next_try = now + RETRY_INTERVAL}
        record.bindings[index] = request
    end
    -- Store scalars, never engine temporary Vector3 values across frames.
    request.r, request.g, request.b, request.strength = r, g, b, strength
    if request.status == "waiting" or request.status == "failed" then return end
    if not attempt(world, id, request) then
        request.status = "waiting"
        request.deadline, request.next_try = now + RETRY_WINDOW, now + RETRY_INTERVAL
        request.attempts = 1
        waiting = waiting + 1
    end
end

function P.update(dt, mod)
    if not mod:is_enabled() then P.clear(); return end
    now = now + math.max(0, tonumber(dt) or 0)
    for world, ids in pairs(materials) do
        -- A missing world registry cannot authorize a native call on a saved handle.
        if not P.world_registered(world) then
            P.forget(world)
        else
            for id, record in pairs(ids) do
                if not World.are_particles_playing(world, id) then
                    P.forget(world, id)
                else
                    for _, request in pairs(record.bindings) do
                        if request.status == "waiting" and (now >= request.next_try or now >= request.deadline) then
                            local done = attempt(world, id, request)
                            if not done and (now >= request.deadline or request.attempts >= MAX_ATTEMPTS) then
                                request.status = "failed"
                                waiting, failed = waiting - 1, failed + 1
                                local key = record.name .. "/" .. request.binding.cloud
                                if not warned[key] then
                                    warned[key] = true
                                    mod:warning("%s", mod:localize("warning_fx_parameter", request.binding.cloud, record.name))
                                end
                            elseif not done then
                                request.next_try = now + RETRY_INTERVAL
                            end
                        end
                    end
                end
            end
        end
    end
end

function P.available(api, selection)
    for name in pairs(selection.resources) do
        if not api.can_get_resource("particles", name) then return false end
    end
    return true
end
local function variable(world,id,resource,name,value)
    local index = World.find_particles_variable(world,resource,name)
    if index and index >= 0 then World.set_particles_variable(world,id,index,value) end
end
function P.apply(world,id,name,mod,colors,selection,brightness,volume)
    -- These native stage carriers keep callback ownership but have no draws.
    -- Their former materials no longer exist in the particle instance.
    if name:match('/ice_forcesword_2h_stage2$') or name:match('/ice_forcesword_2h_stage2_loop$') then return end
    local entry = selection.resources[name]
    if not entry then return end
    local r,g,b=colors.rgb(mod,entry.group)
    local strength=colors.number(mod,entry.group .. "_strength",1,0,5) * (brightness or 1)
    for index,channel in ipairs({"r","g","b"}) do
        local value=({r,g,b})[index]*strength
        variable(world,id,name,"alter_"..channel,Vector3(value,value,value))
    end
    local size=entry.group=="body" and colors.number(mod,"body_size",1,.25,2.5) * (volume or 1) or 1
    variable(world,id,name,"alter_size",Vector3(size,size,size))
    variable(world,id,name,"alter_strength",Vector3(strength,strength,strength))
    for index, binding in ipairs(entry.materials) do
        apply_material(world,id,name,binding,index,r,g,b,strength)
    end
end
function P.aura(world,id,name,mod,colors,strength,volume)
    local r,g,b=colors.rgb(mod,"aura")
    local gain=strength*4
    variable(world,id,name,"energy_rgb",Vector3(r*gain,g*gain,b*gain))
    for index,channel in ipairs({"r","g","b"}) do
        local v=({r,g,b})[index]*gain
        variable(world,id,name,"energy_"..channel,Vector3(v,v,v))
    end
    -- Edge flashes stay narrow at every charge tier and menu setting.
    local size=math.min(1,colors.number(mod,"aura_size",1,.25,2.5)*(volume or 1))
    variable(world,id,name,"energy_size",Vector3(size,size,size))
    for _,layer in ipairs({{"energy_flashes","material_variable_33023669","material_variable",5},
                           {"energy_smoke","lerp_color_b","intensity",1}}) do
        if World.has_particles_material and World.has_particles_material(world,id,layer[1]) then
            World.set_particles_material_vector3(world,id,layer[1],layer[2],Vector3(r,g,b))
            World.set_particles_material_scalar(world,id,layer[1],layer[3],layer[4]*gain)
        end
    end
end
return P
