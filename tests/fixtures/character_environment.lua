-- Synthetic engine boundary. This verifies invariants, not game API compatibility.
hooks, spawned, deletions, released, requests = {}, {}, {}, {}, {}
world = {}
native, native_arms = {alive=true}, {alive=true}
actor = {_unit=native, _first_person_unit=native_arms, _player={}, _equipment={}, restored=0}
function actor:force_update_item_visibility() self.restored=self.restored+1 end
mod = {enabled=true}
function mod:is_enabled() return self.enabled end
function mod:get(key) if key=='first_person_arms' then return true end end
function mod:hook(class, name, callback) hooks[class..':'..name]=callback end
mod.hook_safe = mod.hook
function mod:hook_enable() end
function mod:error(message) error(message) end
api = {}
function api.is_api_compatible(version) return version==1 end
function api.acquire(owner, name, callback)
    local ticket={name=name}
    requests[#requests+1]={ticket=ticket, callback=callback}
    return ticket
end
function api.release(ticket) released[#released+1]=ticket end
function get_mod(name) if name=='CustomAssets' then return api else return mod end end
function resolve_requests()
    local pending=requests; requests={}
    for _,request in ipairs(pending) do request.callback(request.ticket, {}, nil) end
end
spawner = {}
function spawner:spawn_unit(resource, pose)
    assert(not world.destroyed, 'spawn after world teardown')
    local unit={alive=true,resource=resource}
    spawned[#spawned+1]=unit
    return unit
end
function spawner:mark_for_deletion(unit)
    assert(not world.destroyed, 'deletion after world teardown')
    assert(unit~=native and unit~=native_arms, 'native equipment ownership violation')
    deletions[#deletions+1]=unit
end
Managers = {state={unit_spawner=spawner}}
Unit = {}
function Unit.alive(unit) return unit.alive end
function Unit.world_pose() return {} end
function Unit.set_unit_visibility(unit, visible) unit.visible=visible end
function Unit.set_unit_culling() end
function Unit.set_shader_pass_flag_for_meshes_in_unit_and_childs() end
World = {LINK_MODE_NODE_NAME=1}
function World.link_unit(w, child, _, parent)
    assert(not w.destroyed)
    assert(parent==native or parent==native_arms)
    child.parent=parent
end
function init_actor()
    hooks['PlayerUnitVisualLoadoutExtension:init'](actor, {world=world}, native,
        {archetype={breed='human',name='veteran'}})
    hooks['PlayerUnitVisualLoadoutExtension:_update_item_visibility'](actor, true)
end
