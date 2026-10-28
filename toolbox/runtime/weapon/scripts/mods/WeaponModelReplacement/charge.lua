local C = {}
C.resource = "content/mods/weapon_model_replacement/ice_charge_aura"
C.wolf_resource = "content/mods/weapon_model_replacement/violet_charge_aura"
function C.resource_for(record) return record.profile and record.profile.palette=='wolf' and C.wolf_resource or C.resource end
function C.is_resource(name) return name==C.resource or name==C.wolf_resource end

function C.is_wielded(binding)
    if not binding then return false end
    local controller = binding.controller or binding.power_controller or binding.stage_controller
    if not controller then return false end
    local loadout = binding.loadout or controller._visual_loadout_extension
    local inventory = loadout and loadout._inventory_component
    local slot = inventory and inventory.wielded_slot or (loadout and loadout._wielded_slot)
    return slot ~= nil and slot == (binding.slot_name or controller._slot_name)
end

-- Read the weapon's native thresholds; never infer charge from psyker peril.
function C.level(binding)
    if not binding then return 0 end
    local component=binding.component or {}
    local count = tonumber(component.num_special_charges) or 0
    local level = 0
    -- Some item variants do not expose thresholds to the effect controller.
    -- Force-sword charges are still a small counter (usually 0..4); keep the
    -- visual state useful in that case instead of waiting for impossible 10/20.
    local thresholds = binding.thresholds
    if type(thresholds) ~= "table" or #thresholds == 0 then
        thresholds = {{name="middle",threshold=1},{name="high",threshold=3}}
    end
    for _, entry in ipairs(thresholds) do
        if count >= entry.threshold then
            local value = entry.name == "high" and 2 or (entry.name == "middle" and 1 or 0)
            level = math.max(level, value)
        end
    end
    if count > 0 and level == 0 then level = 1 end
    if component.special_active == true then level=math.max(level,1) end
    return level
end

function C.factors(binding, mod, colors, group)
    local level = C.level(binding)
    local prefix = group == "aura" and "aura_two_" or "charge_two_"
    return level == 2 and colors.number(mod,prefix .. "strength",1.6,1,3) or 1,
        level == 2 and colors.number(mod,prefix .. "size",1.12,1,1.5) or 1, level
end

function C.stop(record)
    local id = record.aura_id
    record.aura_id, record.aura_signature = nil, nil
    record.aura_failed_signature = nil
    if id and World.are_particles_playing(record.world,id) then World.destroy_particles(record.world,id) end
end

function C.update(record,binding,wielded,revision,mod,colors,controls)
    local brightness,size,level = C.factors(binding,mod,colors,"aura")
    local strength = colors.number(mod,"charge_aura_strength",.025,0,5)
    local first = binding and (binding.first_person or (binding.controller and binding.controller._first_person_extension))
    local in_first = first and first:is_in_first_person_mode() == true
    -- Native stage FX follow num_special_charges even while special_active is
    -- false. The latter only gates the temporary special-attack surface.
    if not wielded or level == 0 or strength == 0
        or record.first_person ~= (in_first == true) then C.stop(record); return end
    local signature = tostring(revision)..":"..level
    if record.aura_failed_signature == signature then return end
    if record.aura_id and not World.are_particles_playing(record.world,record.aura_id) then
        record.aura_id,record.aura_signature = nil,nil
    end
    if record.aura_id and record.aura_signature == signature then return end
    local ok,err = pcall(function()
        if not record.aura_id then
            record.aura_id = World.create_particles(record.world,C.resource_for(record),Vector3.zero(),nil,nil,binding.particle_group_id)
            if not record.aura_id then error(mod:localize("error_aura_spawn")) end
            World.link_particles(record.world,record.aura_id,record.visual,1,Matrix4x4.identity(),"destroy")
            World.set_particles_use_custom_fov(record.world,record.aura_id,record.first_person)
        end
        controls.aura(record.world,record.aura_id,C.resource_for(record),mod,colors,strength*brightness,size)
        record.aura_signature = signature
    end)
    if not ok then
        C.stop(record); record.aura_failed_signature = signature
        mod:warning("%s",mod:localize("warning_aura_disabled",tostring(err)))
    end
end
return C
