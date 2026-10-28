-- Local visual ownership API. No network or game tables are modified.
local mod=get_mod("ModelReplacementRegistry")
local providers={}
local dirty=false
local api={version=2}
mod.api=api

function api.register(owner,spec)
    assert(type(spec.id)=="string" and type(spec.matches)=="function" and type(spec.ready)=="function" and type(spec.refresh)=="function")
    assert(owner and type(owner.get)=="function" and type(owner.is_enabled)=="function","Provider owner must be a DMF mod")
    assert(not providers[spec.id] or providers[spec.id].owner==owner,"Provider ID already belongs to another mod: "..spec.id)
    providers[spec.id]={owner=owner,spec=spec}
    dirty=true
end
function api.unregister(id,owner)
    local p=providers[id]
    if p and p.owner==owner then providers[id]=nil;dirty=true end
end
function api.changed() dirty=true end

local function provider_ready(id,p)
    local ok,value=pcall(p.spec.ready)
    if not ok then
        local message=tostring(value)
        if p.ready_error~=message then
            p.ready_error=message
            mod:error("%s readiness failed: %s",id,message)
        end
        return false
    end
    p.ready_error=nil
    return value==true
end

-- Same class uses one owner: larger user priority, then stable identifier.
-- Availability is checked before hiding vanilla equipment or choosing an owner.
function api.winner(class,breed,surface)
    if type(class)~="string" then return nil end
    local best,best_priority
    for id,p in pairs(providers) do
        local owner,spec=p.owner,p.spec
        local menu=surface=="preview"
        local supported_breeds=spec.supported_breeds
        local breed_supported=supported_breeds and supported_breeds[breed]==true or (not supported_breeds and breed=="human")
        local enabled=owner:is_enabled()
        if spec.enabled then
            local ok,value=pcall(spec.enabled)
            enabled=enabled and ok and value==true
        else
            enabled=enabled and owner:get("model_enabled")~=false
        end
        local match_ok,match_value=pcall(spec.matches,class,surface,breed)
        local matches=match_ok and match_value==true
        local menu_allowed=owner:get("menu_previews")~=false
        if spec.menu_previews then
            local ok,value=pcall(spec.menu_previews)
            menu_allowed=ok and value==true
        end
        if breed_supported and enabled and matches and (not menu or menu_allowed) and provider_ready(id,p) then
            local priority_value=owner:get("replacement_priority")
            if spec.priority then
                local ok,value=pcall(spec.priority)
                priority_value=ok and value or nil
            end
            local priority=tonumber(priority_value) or 0
            if priority~=priority then priority=0 end
            if not best or priority>best_priority or (priority==best_priority and id<best) then
                best,best_priority=id,priority
            end
        end
    end
    return best
end
function api.actor_allowed(player)
	if player == nil then return false end
	local controller = get_mod("AnimeModelReplacement")
	if controller and controller.should_replace_player then
		return controller.should_replace_player(player) == true
	end
	return true
end
function api.owns(id,class,breed,surface,player)
	if player ~= nil and not api.actor_allowed(player) then return false end
    return api.winner(class,breed,surface)==id
end
function api.providers()
    local result={}
    for id in pairs(providers) do result[#result+1]=id end
    table.sort(result)
    return result
end

-- Defer cross-provider refresh until the next update to avoid hook recursion.
mod.update=function()
    if not dirty then return end
    dirty=false
    local snapshot={}
    for id,p in pairs(providers) do snapshot[#snapshot+1]={id,p} end
    table.sort(snapshot,function(a,b) return a[1]<b[1] end)
    for _,entry in ipairs(snapshot) do
        local id,p=entry[1],entry[2]
        if providers[id]==p then
            local ok,err=pcall(p.spec.refresh)
            if not ok then mod:error("%s refresh failed: %s",id,tostring(err)) end
        end
    end
end
mod.on_unload=function() providers={};dirty=false end
