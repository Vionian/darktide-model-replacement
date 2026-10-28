local V = {}
function V.install(mod, selected)
    local applied, last_unit, last_time, last_height
    function V.restore()
        if not applied then return end
        local a = applied; applied = nil
        if not Unit.alive(a.unit) then return end
        local current, expected = Unit.local_position(a.unit,a.node), a.position:unbox()
        if Vector3.length(current-expected) < .0001 then
            Unit.set_local_position(a.unit,a.node,current-a.offset:unbox())
            World.update_unit_and_children(a.world,a.unit)
        end
    end
    local function apply(self, unit, dt, t)
        if not mod:is_enabled() or not self._is_local_unit or not self:is_in_first_person_mode() then return end
        local loadout = ScriptUnit.has_extension(self._unit,'visual_loadout_system')
        local inventory = loadout and loadout._inventory_component
        local slot = loadout and loadout._equipment and loadout._equipment[inventory and inventory.wielded_slot]
        if not slot or not selected(slot.unit_1p) then V.restore(); last_unit=nil; return end
        local fp = self._first_person_unit
        if not fp or not Unit.alive(fp) then V.restore(); last_unit=nil; return end
        local setting=slot and slot.item and slot.item.weapon_template and slot.item.weapon_template:match('^powersword_2h') and 'fp_height_zealot_cm' or 'fp_height_cm'
        local cm = tonumber(mod:get(setting)) or 3
        if cm ~= cm then cm = 3 end
        cm = math.max(0,math.min(8,cm))
        if cm == 0 then V.restore(); last_unit=nil; return end
        -- update_unit_position is the game's viewmodel placement path. The
        -- weapon and both hands are children of node 1; ap_aim is not the
        -- reliable viewmodel root and is overwritten by the native update.
        -- Other installed viewmodel mods also move this root after placement.
        if t ~= nil and last_unit == fp and last_time == t and last_height == cm then return end
        local node = 1
        local offset = Vector3(0,0,cm*.01)
        local position = Unit.local_position(fp,node)+offset
        Unit.set_local_position(fp,node,position)
        World.update_unit_and_children(self._world,fp)
        applied = {unit=fp,node=node,world=self._world,position=Vector3Box(position),offset=Vector3Box(offset)}
        last_unit,last_time,last_height=fp,t,cm
    end
    mod:hook_safe('PlayerUnitFirstPersonExtension','update_unit_position',apply)
    function V.forget_world(world) if applied and applied.world==world then applied=nil end end
    return V
end
return V
