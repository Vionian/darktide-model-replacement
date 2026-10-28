local C = {}
local fixed={body_size=1.05,aura_size=.85,charge_two_strength=1.25,charge_two_size=1.04,
    aura_two_strength=1.3,aura_two_size=1.04}
function C.number(mod,key,fallback,minimum,maximum)
    local strength=tonumber(mod:get('wolf_fx_strength')) or 1
    if strength~=strength then strength=1 end
    strength=math.max(0,math.min(2,strength))
    local value=fixed[key]
    if key=='charge_aura_strength' then value=.20*strength
    elseif key:match('_strength$') and not key:match('_two_strength$') then value=strength end
    value=value or fallback
    return math.max(minimum or 0,math.min(maximum or 255,value))
end
function C.rgb(_,group)
    -- Electric blue highlights, violet blade field and a subdued purple halo.
    if group=='wave' then return .22,.34,1 end
    if group=='utility' then return .38,.12,1 end
    if group=='aura' then return .30,.10,1 end
    return .32,.10,1
end
return C
