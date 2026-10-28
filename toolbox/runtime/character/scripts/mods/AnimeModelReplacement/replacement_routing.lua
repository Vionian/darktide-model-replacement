local M = {}

local CLASS_ALIASES = {
    class_cryptic = "cryptic",
    skitarius = "cryptic",
    skitarius_soldier = "cryptic",
}

local function class_name(value)
    if type(value) == "table" then
        value = value.name
    end
    if type(value) ~= "string" then
        return nil
    end
    return string.lower(value)
end

function M.normalize_class(value, class_set)
    local name = class_name(value)
    if not name then
        return nil
    end
    if class_set[name] then
        return name
    end
    local alias = CLASS_ALIASES[name]
    return alias and class_set[alias] and alias or nil
end

function M.actor_allowed(replace_teammates, player, local_player)
    if not player then
        return false
    end
    return replace_teammates ~= false or player == local_player
end

local function safe_value(object, key)
    if not object then
        return nil
    end
    local ok, value = pcall(function() return object[key] end)
    if not ok then
        return nil
    end
    if type(value) == "function" then
        ok, value = pcall(value, object)
        return ok and value or nil
    end
    return value
end

local function profile_for(player)
    local profile = safe_value(player, "profile")
    if type(profile) == "table" then
        return profile
    end
    return nil
end

local function player_class(player)
    local profile = profile_for(player)
    local archetype = profile and profile.archetype
    return class_name(archetype)
end

local function identity_key(player)
    return table.concat({
        tostring(safe_value(player, "peer_id") or ""),
        tostring(safe_value(player, "local_player_id") or ""),
        tostring((profile_for(player) or {}).character_id or ""),
    }, "\0")
end

local function stable_sort_key(map_key, player)
    return identity_key(player) .. "\0" .. tostring(map_key or "")
end

function M.variant_for_player(player, class, variants, base_variant, players, local_player, class_set)
    if not player or type(variants) ~= "table" or #variants < 2 then
        return base_variant
    end

    class = M.normalize_class(class, class_set)
    if not class or M.normalize_class(player_class(player), class_set) ~= class then
        return base_variant
    end

    local base_index = 1
    for index, variant in ipairs(variants) do
        if variant == base_variant then
            base_index = index
            break
        end
    end

    local entries = {}
    for map_key, candidate in pairs(players or {}) do
        if candidate and M.normalize_class(player_class(candidate), class_set) == class then
            entries[#entries + 1] = {
                player = candidate,
                key = identity_key(candidate),
                sort_key = stable_sort_key(map_key, candidate),
            }
        end
    end
    table.sort(entries, function(a, b) return a.sort_key < b.sort_key end)

    local player_key = identity_key(player)
    local local_key = local_player and identity_key(local_player)
    local player_index, local_index
    for index, entry in ipairs(entries) do
        if entry.player == player or entry.key == player_key then
            player_index = index
        end
        if local_player and (entry.player == local_player or entry.key == local_key) then
            local_index = index
        end
    end
    if not player_index then
        return base_variant
    end

    local offset = local_index and (player_index - local_index) % #variants or player_index - 1
    return variants[(base_index - 1 + offset) % #variants + 1]
end

return M
