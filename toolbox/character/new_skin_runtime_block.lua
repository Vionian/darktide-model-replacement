local costume_catalog = mod:io_dofile("AnimeModelReplacement/scripts/mods/AnimeModelReplacement/costume_catalog")[MODEL_ID]
local OUTFITS, OUTFIT_CONFIGS, OUTFIT_VARIANTS = {}, {}, {}
local function resolve_outfit()
    local selection = opt(costume_catalog.setting) or "original"
    for _, entry in ipairs(costume_catalog.outfits) do
        if entry.id == selection then
            local variant = math.max(1, math.min(entry.variants, math.floor(tonumber(opt(entry.asset .. "_variant")) or 1)))
            return entry.id .. (variant > 1 and "_v" .. variant or "")
        end
    end
    return "original"
end
local function costume_setting_changed(id)
    if id == costume_catalog.setting then return true end
    for _, entry in ipairs(costume_catalog.outfits) do
        if id == entry.asset .. "_variant" then return true end
    end
    return false
end
for _, entry in ipairs(costume_catalog.outfits) do
    for variant = 1, entry.variants do
        local suffix = variant > 1 and "_v" .. variant or ""
        local key, asset = entry.id .. suffix, entry.asset .. suffix
        OUTFIT_VARIANTS[#OUTFIT_VARIANTS + 1] = key
        OUTFITS[key] = {body=asset, arms=asset .. "_arms", root="content/mods/" .. asset .. "/"}
        if key == "original" then
            OUTFIT_CONFIGS[key] = {jiggle=jiggle_config, proportion=proportion_config}
        else
            local path = "AnimeModelReplacement/scripts/mods/" .. MODEL_ID .. "/" .. asset
            OUTFIT_CONFIGS[key] = {jiggle=mod:io_dofile(path .. "_jiggle_bones"),
                                  proportion=mod:io_dofile(path .. "_proportion_bones")}
        end
    end
end
local jiggle_by_outfit = {}
for key, configs in pairs(OUTFIT_CONFIGS) do jiggle_by_outfit[key] = jiggle_module.new(opt, configs.jiggle) end
local selected_outfit = resolve_outfit()
local BODY, ARMS = OUTFITS[selected_outfit].body, OUTFITS[selected_outfit].arms
local function current_jiggle(key) return jiggle_by_outfit[key or selected_outfit] end
jiggle_config, proportion_config = OUTFIT_CONFIGS[selected_outfit].jiggle, OUTFIT_CONFIGS[selected_outfit].proportion
jiggle = current_jiggle(selected_outfit)
