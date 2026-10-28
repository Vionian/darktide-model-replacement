local C = {}
local defaults = {body_size=1.15,aura_size=1.1,charge_aura_strength=.22,
    charge_two_strength=1.45,charge_two_size=1.08,aura_two_strength=1.6,aura_two_size=1.1}
function C.number(mod,key,fallback,minimum,maximum)
    local value
    if key=='charge_aura_strength' then value=.22*(tonumber(mod:get('ice_fx_strength')) or 1)
    elseif key:match('_strength$') and not key:match('_two_strength$') then
        value=tonumber(mod:get('ice_fx_strength')) or 1
    else value=defaults[key] or tonumber(mod:get(key)) or fallback end
    if not value or value~=value then value=fallback end
    return math.max(minimum or 0,math.min(maximum or 255,value))
end
function C.rgb(_,group)
    -- Linear ice colors: a luminous blue body and a near-white cyan wave core.
    if group=='wave' then return .28,.78,1 end
    if group=='utility' then return .18,.62,1 end
    return .16,.67,1
end
return C
