local I = {}

local function shallow_copy(value)
    local result = {}
    for key, entry in pairs(value) do result[key] = entry end
    return result
end

function I.remap(template, native, replacement)
    -- Copy only changed branches. Never mutate the shared template or its network name.
    if type(template) ~= "table" then return template end
    local result = template
    for _, key in ipairs({ "vfx", "vfx_1p", "vfx_3p" }) do
        local entries = template[key]
        local mapped = entries
        for index, entry in ipairs(entries or {}) do
            local effects = entry.effects
            local mapped_effects = effects
            for effect_index, name in ipairs(effects or {}) do
                if name == native then
                    if mapped_effects == effects then mapped_effects = shallow_copy(effects) end
                    mapped_effects[effect_index] = replacement
                end
            end
            if mapped_effects ~= effects then
                if mapped == entries then mapped = shallow_copy(entries) end
                mapped[index] = shallow_copy(entry)
                mapped[index].effects = mapped_effects
            end
        end
        if mapped ~= entries then
            if result == template then result = shallow_copy(template) end
            result[key] = mapped
        end
    end
    return result
end

return I
