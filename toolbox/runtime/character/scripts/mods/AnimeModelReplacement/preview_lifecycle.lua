-- Original profile teardown may call _update_items_visibility before clearing
-- _character_spawn_data. Block every provider while that callback chain runs.
-- io_dofile runs once per provider. Scene ownership and visibility must be
-- shared across every provider, rather than sixteen independent registries.
local controller = get_mod("AnimeModelReplacement")
if controller.__anime_preview_lifecycle then return controller.__anime_preview_lifecycle end
local M = {}
controller.__anime_preview_lifecycle = M
local unpack = unpack
local function pack(...) return { n = select("#", ...), ... } end
local scenes = {}
local subjects = {}
local actors = {}
local installed = false

local function alive(unit)
    return unit ~= nil and Unit.alive(unit)
end

local function intro_active()
    if next(scenes) ~= nil then return true end
    local ui = Managers.ui
    return ui and ui.view_active and ui:view_active("mission_intro_view") or false
end

-- A preview world may contain six possible positions and cinematic actors.
-- Only occupied slots in the owning view represent the actual squad.
function M.allowed(spawner)
    if M.blocked(spawner) or spawner._visible == false
        or spawner._character_toggle_state == false then return false end
    for _, scene in pairs(scenes) do
        if scene.world == spawner._world then
            if scene.leaving then return false end
            for _, slot in pairs(scene.view._spawn_slots or {}) do
                if slot.profile_spawner == spawner then return slot.occupied == true end
            end
            if not scene.rejected[spawner] then
                scene.rejected[spawner] = true
                controller:info("Preview ownership v2: suppressed non-squad preview %s", tostring(spawner._reference_name))
            end
            return false
        end
    end
    return true
end

function M.subject(spawner, unit, asset, cleanup)
    spawner.__anime_portrait_subject = {unit = unit, asset = asset}
    subjects[unit] = {spawner = spawner, cleanup = cleanup}
end

function M.clear_subject(spawner, unit)
    local subject = spawner.__anime_portrait_subject
    if subject and subject.unit == unit then spawner.__anime_portrait_subject = nil end
    if unit then subjects[unit] = nil end
end

function M.blocked(spawner)
    return spawner.__anime_model_teardown_depth ~= nil
end

function M.teardown(spawner, cleanup, original, ...)
    spawner.__anime_model_teardown_depth = (spawner.__anime_model_teardown_depth or 0) + 1
    local args = pack(...)
    local result = pack(pcall(function()
        cleanup(spawner)
        return original(spawner, unpack(args, 1, args.n))
    end))
    local remaining = spawner.__anime_model_teardown_depth - 1
    spawner.__anime_model_teardown_depth = remaining > 0 and remaining or nil
    if not result[1] then error(result[2], 0) end
    return unpack(result, 2, result.n)
end

local function actor_visible(driver)
    if not alive(driver) or intro_active() then return false end
    local visibility = ScriptUnit.has_extension(driver, "player_visibility_system")
    return not visibility or visibility:visible()
end

-- The Endfield 3P body is driven manually, so native recursive visibility and
-- visibility snapshots do not include it. Keep its visibility policy explicit.
function M.actor_subject(unit, driver, wanted)
    if not alive(unit) then return end
    actors[unit] = {driver = driver, wanted = wanted and true or false}
    Unit.set_unit_visibility(unit, wanted and actor_visible(driver) or false, true)
end

function M.release_actor(unit)
    if unit then
        actors[unit] = nil
        -- Engine deletion is queued. Hide immediately, before another render.
        if alive(unit) then Unit.set_unit_visibility(unit, false, true) end
    end
end

local function sync_actors(driver)
    for unit, entry in pairs(actors) do
        if not alive(unit) then
            actors[unit] = nil
        elseif not driver or entry.driver == driver then
            Unit.set_unit_visibility(unit, entry.wanted and actor_visible(entry.driver) or false, true)
        end
    end
end

local function sweep(scene)
    local pending = {}
    for unit, entry in pairs(subjects) do
        if not alive(unit) then
            subjects[unit] = nil
        elseif entry.spawner._world == scene.world and not M.allowed(entry.spawner) then
            pending[#pending + 1] = entry
        end
    end
    for _, entry in ipairs(pending) do
        if entry.cleanup then entry.cleanup(entry.spawner) end
    end
end

local function claim(view)
    local world_spawner = view._world_spawner
    local world = world_spawner and world_spawner:world()
    if not world then return end
    local scene = scenes[view]
    if not scene then
        scene = {view = view, world = world, rejected = setmetatable({}, {__mode = "k"})}
        scenes[view] = scene
        controller:info("Preview ownership v2: mission preparation uses occupied squad slots; hidden actors stay hidden.")
    end
    sweep(scene)
    sync_actors()
end

function M.reset()
    -- Controller hooks are disabled with the mod. Do not retain ownership of a
    -- world whose on_exit may then run without our hook (toggle/reload path).
    for view in pairs(scenes) do scenes[view] = nil end
    local pending = {}
    for _, entry in pairs(subjects) do pending[#pending + 1] = entry end
    for _, entry in ipairs(pending) do
        if entry.cleanup then entry.cleanup(entry.spawner) end
    end
    for unit in pairs(actors) do M.release_actor(unit) end
end

function M.install(mod)
    if installed then return end
    installed = true
    mod:hook_safe(CLASS.MissionIntroView, "_setup_spawn_slots", claim)
    mod:hook_safe(CLASS.MissionIntroView, "update", claim)
    mod:hook(CLASS.MissionIntroView, "on_exit", function(func, self, ...)
        local scene = scenes[self]
        if scene then
            scene.leaving = true
            sweep(scene)
        end
        local args = pack(...)
        local result = pack(pcall(function() return func(self, unpack(args, 1, args.n)) end))
        scenes[self] = nil
        sync_actors()
        if not result[1] then error(result[2], 0) end
        return unpack(result, 2, result.n)
    end)
    local function sync_player(self) sync_actors(self._unit) end
    mod:hook_safe(CLASS.PlayerVisibilityExtension, "hide", sync_player)
    mod:hook_safe(CLASS.PlayerVisibilityExtension, "show", sync_player)
    mod:hook_safe(CLASS.PlayerUnitVisualLoadoutExtension, "update", sync_player)
    mod:hook_safe(CLASS.PlayerHuskVisualLoadoutExtension, "update", sync_player)
end

return M
