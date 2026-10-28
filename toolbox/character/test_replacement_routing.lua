local routing = dofile("scripts/mods/AnimeModelReplacement/replacement_routing.lua")
local definitions = dofile("scripts/mods/AnimeModelReplacement/model_definitions.lua")

local classes = {
    veteran = true,
    zealot = true,
    psyker = true,
    adamant = true,
    broker = true,
    cryptic = true,
}

for _, model in ipairs(definitions.models) do
    if model.id ~= "none" then
        assert(model.breeds.human == true, model.id .. ": human breed support missing")
        assert(model.breeds.cryptic == true, model.id .. ": cryptic breed support missing")
        assert(model.breeds.ogryn ~= true, model.id .. ": Ogryn must remain excluded")
    end
end

local function equal(actual, expected, label)
    assert(actual == expected, label .. ": expected " .. tostring(expected) .. ", got " .. tostring(actual))
end

equal(routing.normalize_class("cryptic", classes), "cryptic", "canonical career")
equal(routing.normalize_class("Skitarius", classes), "cryptic", "Skitarius alias")
equal(routing.normalize_class({ name = "class_cryptic" }, classes), "cryptic", "profile alias")
equal(routing.normalize_class("unknown", classes), nil, "unknown career")

local me = {}
local teammate = {}
local bot = {}
equal(routing.actor_allowed(true, teammate, me), true, "teammate enabled")
equal(routing.actor_allowed(false, me, me), true, "self remains enabled")
equal(routing.actor_allowed(false, teammate, me), false, "teammate disabled")
equal(routing.actor_allowed(true, nil, me), false, "missing player rejected")

local function player(peer, player_id, archetype)
    return {
        peer_id = function() return peer end,
        local_player_id = function() return player_id end,
        profile = function()
            return { character_id = peer .. "-" .. player_id, archetype = { name = archetype } }
        end,
    }
end

local local_cryptic = player("peer-a", 1, "cryptic")
local remote_cryptic = player("peer-b", 1, "cryptic")
local bot_cryptic = player("peer-c", 1, "cryptic")
local other_class = player("peer-d", 1, "psyker")
local variants = { "original", "ink_mist", "short_skirt", "lolita" }
local roster = {
    bot = bot_cryptic,
    remote = remote_cryptic,
    local_player = local_cryptic,
    unrelated = other_class,
}

equal(routing.variant_for_player(local_cryptic, "cryptic", variants, "original", roster, local_cryptic, classes),
    "original", "local keeps selected outfit")
equal(routing.variant_for_player(remote_cryptic, "cryptic", variants, "original", roster, local_cryptic, classes),
    "ink_mist", "first duplicate receives next outfit")
equal(routing.variant_for_player(bot_cryptic, "cryptic", variants, "original", roster, local_cryptic, classes),
    "short_skirt", "bot receives following outfit")

local daniya_variants = { "red", "blue" }
equal(routing.variant_for_player(remote_cryptic, "cryptic", daniya_variants, "red", roster, local_cryptic, classes),
    "blue", "two-form model cycles")

print("replacement routing tests passed")
