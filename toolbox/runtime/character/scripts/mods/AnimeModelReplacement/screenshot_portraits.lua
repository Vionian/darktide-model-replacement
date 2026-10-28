-- Original screenshot RGB + an offline alpha matte. Keep the native HUD frame,
-- insignia, status shading and atlas request lifetime; override only its icon.
local M = {}
local portraits = {
    RoshiaReplacement = "roshia",
    ChenqianyuReplacement = "chenqianyu",
    GilbertaReplacement = "gilberta",
    LiinoReplacement = "liino",
    MifuReplacement = "mifu",
    PerlicaReplacement = "perlica",
    TangtangReplacement = "tangtang",
    YvonneReplacement = "yvonne",
    ZhuangfangyiReplacement = "zhuangfangyi",
    AitelaReplacement = "aitela",
    LaiwantingReplacement = "laiwanting",
    SaixiReplacement = "saixi",
}
local fields = {"texture_icon", "rows", "columns", "grid_index", "use_placeholder_texture"}

function M.install(mod)
    local panels = setmetatable({}, {__mode = "k"})
    local textures = {}
    local stopped = false
    local owner = {} -- Own only these tickets, never the providers' model assets.

    local function widget_for(panel)
        local widget = panel._widgets_by_name and panel._widgets_by_name.player_icon
        local style = widget and widget.style and widget.style.texture
        return widget, style and style.material_values
    end

    local function snapshot(panel)
        local widget, values = widget_for(panel)
        if not values then return end
        local state = {material = widget.content.texture}
        for _, key in ipairs(fields) do state[key] = values[key] end
        return state
    end

    local function write(panel, state)
        local widget, values = widget_for(panel)
        if not values or not state then return end
        local changed = widget.content.texture ~= state.material
        widget.content.texture = state.material
        for _, key in ipairs(fields) do
            changed = changed or values[key] ~= state[key]
            values[key] = state[key]
        end
        return changed
    end

    local function restore(panel)
        local baseline = panels[panel]
        if baseline then
            local changed = write(panel, baseline)
            panels[panel] = nil
            local widget = widget_for(panel)
            if widget and changed then widget.dirty = true end
        end
    end

    local function selected_texture(panel)
        if stopped or panel.__deleted or not mod:is_enabled() or mod:get("model_enabled") == false then return end
        local player = panel._player
        local profile = player and not player.__deleted and player:profile()
        local archetype = profile and profile.archetype
        if not archetype or (archetype.breed ~= "human" and archetype.breed ~= "cryptic") then return end
        local provider = mod.model_for_class(archetype.name)
        local asset = portraits[provider]
        if not asset or not mod.should_replace(provider, archetype.name, "body", archetype.breed) then return end
        local registry = get_mod("ModelReplacementRegistry")
        local api = registry and registry.api
        if not api or api.version ~= 2 or api.winner(archetype.name, archetype.breed, "body") ~= provider then return end
        local record = textures[asset]
        if not record then
            local custom = get_mod("CustomAssets")
            if not custom or not custom.acquire then return end
            local resource = "content/mods/" .. asset .. "/" .. asset .. "_portrait"
            -- Cooked-folder manifests may expose texture names as opaque hashes.
            -- The owning logical asset is stable across both discovery modes.
            local ticket, err = custom.acquire(owner, "AnimeModelReplacement:" .. asset, nil,
                {resident = true, reference_name = "AnimeScreenshotPortrait:" .. asset})
            record = {ticket = ticket, resource = resource}
            textures[asset] = record
            if not ticket then mod:error("Screenshot portrait unavailable (%s): %s", asset, tostring(err)) end
        end
        if record.ticket and record.ticket.status == "loaded" then return record.resource, profile end
    end

    local function apply(panel)
        -- A synchronous native capture callback can also run inside update.
        -- Always unwrap that override before saving the next native baseline.
        restore(panel)
        local resource, profile = selected_texture(panel)
        local widget, values = widget_for(panel)
        if not resource or not values then return end
        panels[panel] = snapshot(panel)
        values.texture_icon = resource
        values.rows, values.columns, values.grid_index = 1, 1, 0
        values.use_placeholder_texture = 0
        widget.content.texture = panel:_get_player_portrait_frame_material(profile)
    end

    mod:hook("HudElementPlayerPanelBase", "_update_player_features", function(func, self, ...)
        local previous = snapshot(self)
        local baseline = panels[self]
        -- Let native callbacks/status/frame changes operate on their own values.
        if baseline then write(self, baseline); panels[self] = nil end
        func(self, ...)
        apply(self)
        local current = snapshot(self)
        if previous and current then
            local widget = widget_for(self)
            if previous.material ~= current.material then widget.dirty = true end
            for _, key in ipairs(fields) do
                if previous[key] ~= current[key] then widget.dirty = true; break end
            end
        end
    end)
    mod:hook("HudElementPlayerPanelBase", "_cb_set_player_icon", function(func, self, ...)
        restore(self)
        func(self, ...)
        apply(self)
    end)
    mod:hook("HudElementPlayerPanelBase", "_cb_set_player_frame", function(func, self, ...)
        restore(self)
        func(self, ...)
        apply(self)
    end)
    mod:hook("HudElementPlayerPanelBase", "_cb_unset_player_icon", function(func, self, ...)
        panels[self] = nil
        return func(self, ...)
    end)
    mod:hook("HudElementPlayerPanelBase", "destroy", function(func, self, ...)
        restore(self)
        return func(self, ...)
    end)

    local function suspend()
        for panel in pairs(panels) do restore(panel) end
    end
    local function shutdown()
        stopped = true
        suspend()
        local custom = get_mod("CustomAssets")
        if custom and custom.release_owner then custom.release_owner(owner) end
        textures = {}
    end
    return {suspend = suspend, shutdown = shutdown}
end

return M
