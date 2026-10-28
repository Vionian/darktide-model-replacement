local E = {}
function E.install(mod,selection,records,is_ready,selected)
    local path='WeaponModelReplacement/scripts/mods/WeaponModelReplacement/'
    local controls=mod:io_dofile(path..'particle_controls')
    local colors=mod:io_dofile(path..'ice_colors')
    local wolf_colors=mod:io_dofile(path..'wolf_colors')
    local charge=mod:io_dofile(path..'charge')
    local appearance=mod:io_dofile(path..'appearance')
    local impact=mod:io_dofile(path..'impact')
    local effects=mod:io_dofile(path..'fx_manifest')
    local wolf_effects=mod:io_dofile(path..'wolf_fx_manifest')
    local resources,fx,bindings,particles,writable={}, {ice={},wolf={}}, {},{},{}
    local resource_colors,resource_profiles={},{}
    local context,revision=false,0
    for palette,manifest in pairs({ice=effects,wolf=wolf_effects}) do
        for native,entry in pairs(manifest) do
            fx[palette][native]=entry.resource;resources[entry.resource]=entry
            resource_colors[entry.resource]=palette=='wolf' and wolf_colors or colors
            resource_profiles[entry.resource]={palette=palette}
        end
    end
    resource_profiles[charge.resource],resource_profiles[charge.wolf_resource]={palette='ice'},{palette='wolf'}
    local config={resources=resources}
    local function enabled(profile)
        return mod:is_enabled() and mod:get(profile and profile.palette=='wolf' and 'wolf_effects' or 'ice_effects')~=false and is_ready()
    end
    local function palette_colors(profile) return profile and profile.palette=='wolf' and wolf_colors or colors end
    local function alive(unit) return unit and Unit.alive(unit) end
    local function pack(...) return {n=select('#',...),...} end
    local function target(loadout)
        if not mod:is_enabled() or not is_ready() or not loadout then return false end
        local inv=loadout._inventory_component
        local slot=loadout._equipment and loadout._equipment[inv and inv.wielded_slot or loadout._wielded_slot]
        local profile=slot and selection.profile(slot.item)
        return profile and enabled(profile) and profile.effects==true and (records[slot.unit_1p] or records[slot.unit_3p])~=nil and profile or false
    end
    local function target_fx(extension)
        return extension and target(extension._visual_loadout_extension or
            (extension._fx_extension and extension._fx_extension._visual_loadout_extension)) or false
    end
    local function attacker(unit)
        return alive(unit) and target(ScriptUnit.has_extension(unit,'visual_loadout_system')) or false
    end
    local function particle_group(world,group)
        if group==nil then return false end
        local extensions=Managers.state and Managers.state.extension
        local system=extensions and extensions:system('fx_system')
        if not system or system._world~=world then return false end
        for unit,id in pairs(system.unit_to_particle_group_lookup or {}) do
            if id==group then local profile=attacker(unit);if profile then return profile end end
        end
        return false
    end
    local function with_context(func,value,...)
        local before=context;context=value
        local result=pack(pcall(func,...));context=before
        if not result[1] then error(result[2],0) end
        return unpack(result,2,result.n)
    end
    local function forget(world,id)
        for _,record in pairs(records) do
            if record.world==world and record.aura_id==id then
                record.aura_id,record.aura_signature=nil,nil
            end
        end
        controls.forget(world,id)
        if particles[world] then particles[world][id]=nil;if not next(particles[world]) then particles[world]=nil end end
        if writable[world] then writable[world][id]=nil end
    end
    mod:hook_safe('ForceWeaponEffects','init',function(self,ctx,slot,template,fx_sources,item,unit_1p,unit_3p)
        local profile=selection.family(item); if not profile or not profile.effects then return end
        slot=slot or {}; local root_1p,root_3p=slot.unit_1p or unit_1p,slot.unit_3p or unit_3p
        local binding=bindings[root_1p] or bindings[root_3p] or {}
        binding.controller,binding.world,binding.component=self,ctx.world or self._world,self._inventory_slot_component
        binding.loadout,binding.slot_name=ctx.visual_loadout_extension,slot.name or self._slot_name
        binding.first_person=self._first_person_extension
        binding.particle_group_id=GameParameters.destroy_unmanaged_particles and ctx.player_particle_group_id or nil
        binding.thresholds=binding.thresholds or (template.weapon_special_tweak_data and template.weapon_special_tweak_data.thresholds)
        -- Native slot scripts can be declared on a blade attachment. Their init
        -- unit arguments are then attachment units, while replacement records
        -- are indexed by the slot's equipment roots. Always bind canonical roots.
        if root_1p then bindings[root_1p]=binding end
        if root_3p then bindings[root_3p]=binding end
    end)
    mod:hook_safe('ForceWeaponWindSlashStageEffects','init',function(self,ctx,slot,template,fx_sources,item,unit_1p,unit_3p)
        local profile=selection.family(item); if not profile or not profile.effects then return end
        if not slot then return end
        local root_1p,root_3p=slot.unit_1p or unit_1p,slot.unit_3p or unit_3p
        local binding=bindings[root_1p] or bindings[root_3p] or {controller=self}
        binding.stage_controller=self
        binding.loadout,binding.slot_name=ctx.visual_loadout_extension,slot.name
        binding.world,binding.component=ctx.world or self._world,self._inventory_slot_component
        binding.first_person=binding.first_person or ScriptUnit.has_extension(ctx.owner_unit,'first_person_system')
        binding.thresholds=self._weapon_special_tweak_data and self._weapon_special_tweak_data.thresholds
        binding.particle_group_id=GameParameters.destroy_unmanaged_particles and ctx.player_particle_group_id or nil
        if root_1p then bindings[root_1p]=binding end
        if root_3p then bindings[root_3p]=binding end
    end)
    mod:hook_safe('PowerWeaponEffects','init',function(self,ctx,slot,template,fx_sources,item,unit_1p,unit_3p)
        local profile=selection.family(item);if not profile or not profile.cover or not slot then return end
        local root_1p,root_3p=slot.unit_1p or unit_1p,slot.unit_3p or unit_3p
        local binding=bindings[root_1p] or bindings[root_3p] or {}
        binding.power_controller,binding.world,binding.component=self,ctx.world or self._world,self._inventory_slot_component
        binding.loadout,binding.slot_name=ctx.visual_loadout_extension,slot.name
        binding.first_person=self._first_person_extension
        binding.thresholds=template.weapon_special_tweak_data and template.weapon_special_tweak_data.thresholds
        if root_1p then bindings[root_1p]=binding end;if root_3p then bindings[root_3p]=binding end
    end)
    mod:hook_safe('ForceWeaponEffects','destroy',function(self)
        for root,binding in pairs(bindings) do
            if binding.controller==self then if records[root] then E.retire(records[root]) end;bindings[root]=nil end
        end
    end)
    mod:hook_safe('PowerWeaponEffects','destroy',function(self)
        for root,binding in pairs(bindings) do
            if binding.power_controller==self then if records[root] then E.retire(records[root]) end;bindings[root]=nil end
        end
    end)
    for _,entry in ipairs({
        {'PlayerUnitFxExtension','_create_particles_wrapper'},
        {'PlayerUnitFxExtension','_spawn_moving_player_fx'},
        {'ForceWeaponWindSlashActivationEffects','_update_vfx'},
        {'ForceWeaponWindSlashStageEffects','_update_effects'},
        {'ForceWeaponBlockEffects','_update_vfx'},
        {'ForceWeaponEffects','_update_active'},
        {'WarpChargeVentingEffects','_update_vfx'},
    }) do
        mod:hook(entry[1],entry[2],function(func,self,...) return with_context(func,target_fx(self),self,...) end)
    end
    mod:hook('FxSystem','play_impact_fx',function(func,self,template,position,direction,parameters,source,victim,...)
        local value=attacker(source)
        if value then for native,replacement in pairs(fx[value.palette or 'ice']) do template=impact.remap(template,native,replacement) end end
        return with_context(func,value,self,template,position,direction,parameters,source,victim,...)
    end)
    mod:hook(World,'create_particles',function(func,world,name,...)
        local profile=context or particle_group(world,select(4,...))
        local replacements=profile and enabled(profile) and fx[profile.palette or 'ice']
        local replacement=replacements and replacements[name]
        local id=func(world,replacement or name,...)
        if id then forget(world,id) end
        if id and (replacement or resources[name] or charge.is_resource(name)) then
            particles[world]=particles[world] or {};particles[world][id]=replacement or name
            writable[world]=writable[world] or {};writable[world][id]=true
            if resources[replacement or name] then controls.apply(world,id,replacement or name,mod,resource_colors[replacement or name],config) end
        end
        return id
    end)
    mod:hook(World,'destroy_particles',function(func,world,id,...) forget(world,id);return func(world,id,...) end)
    mod:hook(World,'link_particles',function(func,world,id,unit,node,pose,policy,...)
        local name=writable[world] and writable[world][id] and particles[world] and particles[world][id]
        if name and (name:match('/ice_forcesword_2h_stage2$') or name:match('/ice_forcesword_2h_stage2_loop$')) then
            local record=records[unit]
            if not record then
                for _,candidate in pairs(records) do
                    for _,original in ipairs(candidate.originals) do if original==unit then record=candidate;break end end
                    if record then break end
                end
            end
            if record and alive(record.visual) and record.world==world then
                local binding=bindings[record.root]
                local first=binding and (binding.first_person or (binding.controller and binding.controller._first_person_extension))
                if first then
                    local wanted=first:is_in_first_person_mode()==true
                    for root,candidate in pairs(records) do
                        if bindings[root]==binding and candidate.first_person==wanted and alive(candidate.visual) then record=candidate;break end
                    end
                end
                unit,node,pose=record.visual,1,Matrix4x4.from_translation(Vector3(-.004,.001,.16))
                World.set_particles_use_custom_fov(world,id,record.first_person)
                local chosen=palette_colors(record.profile)
                local brightness,volume=charge.factors(bindings[record.root],mod,chosen)
                controls.apply(world,id,name,mod,chosen,config,brightness,volume)
            end
        end
        return func(world,id,unit,node,pose,policy,...)
    end)
    function E.retire(record)
        local id=record.aura_id
        if id and particles[record.world] and particles[record.world][id]==charge.resource_for(record)
            and controls.world_registered(record.world) then charge.stop(record)
        else record.aura_id,record.aura_signature=nil,nil end
    end
    function E.forget_world(world)
        particles[world],writable[world]=nil,nil;controls.forget(world)
        for root,binding in pairs(bindings) do
            local record=records[root]
            if binding.world==world or (record and record.world==world) then
                bindings[root]=nil
                if record then record.aura_id=nil end
            end
        end
    end
    function E.disable()
        for _,record in pairs(records) do E.retire(record) end
        controls.clear();writable={}
    end
    function E.unused() return not next(particles) end
    function E.settings_changed()
        revision=revision+1
        local list={}
        for world,ids in pairs(particles) do for id,name in pairs(ids) do list[#list+1]={world,id,name} end end
        for _,p in ipairs(list) do
            local world,id,name=p[1],p[2],p[3]
            if not controls.world_registered(world) then forget(world,id)
            elseif not enabled(resource_profiles[name]) then
                if World.are_particles_playing(world,id) then World.destroy_particles(world,id) end
                forget(world,id)
            elseif writable[world] and writable[world][id] and World.are_particles_playing(world,id) then
                controls.apply(world,id,name,mod,resource_colors[name] or colors,config)
            end
        end
    end
    function E.update(dt)
        controls.update(dt,mod)
        for world,ids in pairs(particles) do
            if not controls.world_registered(world) then E.forget_world(world)
            else for id in pairs(ids) do if not World.are_particles_playing(world,id) then forget(world,id) end end end
        end
        for root,record in pairs(records) do
            local binding=bindings[root]
            if mod:is_enabled() and controls.world_registered(record.world) and binding and binding.component and alive(record.root) and alive(record.visual) then
                local chosen=palette_colors(record.profile)
                if record.profile and record.profile.cover then
                    local level=charge.level(binding)
                    local active=enabled(record.profile) and charge.is_wielded(binding)
                        and (level>0 or binding.component.special_active==true)
                    appearance.cover(record,active,mod,chosen,level)
                end
                if enabled(record.profile) and (not record.profile or record.profile.effects) then
                    charge.update(record,binding,charge.is_wielded(binding),revision,mod,chosen,controls)
                else E.retire(record) end
            else E.retire(record) end
        end
    end
    function E.resources_available(api)
        return controls.available(api,config) and api.can_get_resource('particles',charge.resource)
            and api.can_get_resource('particles',charge.wolf_resource)
    end
    return E
end
return E
