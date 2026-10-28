local A = {}
function A.apply(unit, active, mod)
    local value=tonumber(mod:get("emission_strength")) or .5
    if value~=value then value=.5 end
    value=math.max(0,math.min(40,value))
    Unit.set_scalar_for_material(unit,"khravengger_pbr","intensity",value*.25)
    Unit.set_vector3_for_material(unit,"khravengger_pbr","emissive_color",Vector3(1,1,1))
end
function A.cover(record,active,mod,colors,level)
    local r,g,b=colors.rgb(mod,"body")
    local channel_color={r,g,b}
    local strength=active and colors.number(mod,"cover_strength",1,0,5) or 0
    -- Blade-edge ribbons are authored to the cutting surface; never inflate
    -- them across the whole blade, guard or handle when charge level rises.
    local size=1
    local signature=table.concat({tostring(active),tostring(level or 0),strength,size},":")
    if record.cover_signature==signature then return end
    local now=World.time(record.world)
    local changed=record.cover_active~=active
    for index,channel in ipairs({"r","g","b"}) do
        local material="ice_cover_"..channel
        local visible=active and strength*channel_color[index]>0
        Unit.set_mesh_visibility(record.visual,"cover_"..channel.."_mesh_p0",visible)
        Unit.set_mesh_visibility(record.visual,"cover_"..channel.."_mesh_p0_back",visible)
        Unit.set_scalar_for_material(record.visual,material,"intensity",visible and strength*channel_color[index] or 0)
        Unit.set_scalar_for_material(record.visual,material,"power_toggle",active and 1 or 0)
        if changed then
            Unit.set_scalar_for_material(record.visual,material,active and "fade_in" or "fade_out",now)
            if active then Unit.set_scalar_for_material(record.visual,material,"fade_out",-1) end
        end
        -- The serialized cover scene graph uses cover_{r,g,b}_mesh nodes;
        -- the mesh visibility objects have the additional _p0 suffix.
        -- Keep these names separate: Unit.node must address the scene node,
        -- while set_mesh_visibility addresses its compiled mesh object.
        Unit.set_local_scale(record.visual,Unit.node(record.visual,"cover_"..channel.."_mesh"),Vector3(size,size,1))
    end
    record.cover_active=active
    record.cover_signature=signature
end
return A
