-- Only reversible translations. The game retains equipment parent, animation and visibility.
local M={}
local states=setmetatable({}, {__mode='k'})
local function alive(u) return u and Unit.alive(u) end
local function saved(v) return {v.x,v.y,v.z} end
local function vector(v) return Vector3(v[1],v[2],v[3]) end
local function same(a,b) return Vector3.length(a-b)<0.000001 end
local function restore(e)
    if alive(e.unit) then
        local current=Unit.local_position(e.unit,e.node)
        if same(current,vector(e.written)) then Unit.set_local_position(e.unit,e.node,current-vector(e.correction)) end
    end
end
function M.release(owner)
    local state=states[owner]
    if state then
        for _,entry in pairs(state) do restore(entry) end
        states[owner]=nil
    end
end
local function active_slot(owner)
    local inventory=owner._inventory_component
    local data=owner._character_spawn_data
    return inventory and inventory.wielded_slot or owner._locally_wielded_slot or owner._wielded_slot
        or data and data.wielded_slot and data.wielded_slot.name
end
local function contact(slot,unit)
    local item=slot.item
    if not item then return end
    local attach=item.breed_attach_node and item.breed_attach_node[slot.breed_name] or item.attach_node
    local side
    if type(attach)=='string' then
        if string.find(attach,'lefthand',1,true) or string.find(attach,'leftweaponattach',1,true) then side='left' end
        if string.find(attach,'righthand',1,true) or string.find(attach,'rightweaponattach',1,true) then side='right' end
    end
    if not side then
        local right=Unit.has_node(unit,'j_rightweaponattach')
        local left=Unit.has_node(unit,'j_leftweaponattach')
        if right and not left then side='right' elseif left and not right then side='left' end
    end
    if not side then return end
    local anchor='j_'..side..'weaponattach'
    -- A name-mapped anchor child can bypass the carrier root.
    local node=Unit.has_node(unit,anchor) and Unit.node(unit,anchor) or 1
    return 'j_'..side..'hand',node
end
function M.update(owner,world,actor,model,slots,enabled,poses)
    if not (enabled and alive(actor) and alive(model) and slots and poses
        and (poses.arm_pose_policy=='source_lengths_native_rotations'
            or poses.arm_pose_policy=='source_lengths_relaxed_native_rotations')) then
        M.release(owner);return
    end
    local state=states[owner] or {};states[owner]=state
    local active=active_slot(owner)
    local seen={}
    for name,slot in pairs(slots) do
        local unit=slot.unit_3p
        local wielded=(name=='slot_primary' or name=='slot_secondary') and active==name
        if wielded and slot.hidden_3p~=true and alive(unit) and slot.parent_unit_3p==actor then
            local hand,node=contact(slot,unit)
            local pose=hand and poses[hand]
            if pose and Unit.has_node(actor,hand) then
                seen[unit]=true
                local entry=state[unit]
                if entry and entry.node~=node then restore(entry);entry=nil end
                local current=Unit.local_position(unit,node)
                local baseline=current
                if entry and same(current,vector(entry.written)) then baseline=current-vector(entry.correction) end
                local delta=pose.position-Unit.world_position(actor,Unit.node(actor,hand))
                local parent_rotation=Quaternion.multiply(Unit.world_rotation(unit,node),Quaternion.inverse(Unit.local_rotation(unit,node)))
                local correction=Quaternion.rotate(Quaternion.inverse(parent_rotation),delta)
                local written=baseline+correction
                Unit.set_local_position(unit,node,written)
                state[unit]={unit=unit,node=node,written=saved(written),correction=saved(correction)}
            end
        end
    end
    for unit,entry in pairs(state) do
        if not seen[unit] then restore(entry);state[unit]=nil end
    end
end
return M
