local mod = get_mod("AnimeModelReplacement")
local preview_lifecycle = mod:io_dofile("AnimeModelReplacement/scripts/mods/AnimeModelReplacement/preview_lifecycle")
preview_lifecycle.install(mod)
local definitions = mod:io_dofile("AnimeModelReplacement/scripts/mods/AnimeModelReplacement/model_definitions")
mod:io_dofile("AnimeModelReplacement/scripts/mods/AnimeModelReplacement/portrait_framing").install(mod)
local screenshot_portraits = mod:io_dofile("AnimeModelReplacement/scripts/mods/AnimeModelReplacement/screenshot_portraits").install(mod)
local routing = mod:io_dofile("AnimeModelReplacement/scripts/mods/AnimeModelReplacement/replacement_routing")

local CLASSES = {}
local CLASS_SET = {}
local PROVIDERS = {}
local MODEL_BY_ID = {}

for _, class in ipairs(definitions.classes) do
	CLASSES[#CLASSES + 1] = class.id
	CLASS_SET[class.id] = true
end
for _, model in ipairs(definitions.models) do
	MODEL_BY_ID[model.id] = model
	if model.id ~= "none" then
		PROVIDERS[#PROVIDERS + 1] = model.id
	end
end

function mod.model_for_class(class_name)
	class_name = routing.normalize_class(class_name, CLASS_SET)
	if not class_name then return "none" end
	local selected = mod:get("model_" .. class_name)
	for _, provider_id in ipairs(PROVIDERS) do
		if selected == provider_id then
			return selected
		end
	end
	return "none"
end

function mod.is_model_selected(provider_id)
	for _, class_name in ipairs(CLASSES) do
		if mod.model_for_class(class_name) == provider_id then
			return true
		end
	end
	return false
end

function mod.model_supports_breed(provider_id, breed)
	local model = MODEL_BY_ID[provider_id]
	return model and model.breeds and model.breeds[breed] == true or false
end

function mod.is_model_active(provider_id)
	return mod:is_enabled() and mod:get("model_enabled") ~= false and mod.is_model_selected(provider_id)
end

function mod.should_replace(provider_id, class_name, surface, breed)
	if not mod:is_enabled() or mod:get("model_enabled") == false then
		return false
	end
	if not mod.model_supports_breed(provider_id, breed or "human") then
		return false
	end
	if surface == "preview" and mod:get("menu_previews") == false then
		return false
	end
	return mod.model_for_class(class_name) == provider_id
end

local function local_player()
	local player_manager = Managers.player
	if not player_manager then return nil end
	local ok, player = pcall(player_manager.local_player_safe, player_manager, 1)
	return ok and player or nil
end

function mod.should_replace_player(player)
	return routing.actor_allowed(mod:get("replace_teammates"), player, local_player())
end

function mod.variant_for_player(player, class_name, variants, base_variant)
	local player_manager = Managers.player
	if not player_manager then return base_variant end
	local ok, players = pcall(player_manager.players, player_manager)
	if not ok then return base_variant end
	return routing.variant_for_player(player, class_name, variants, base_variant, players,
		local_player(), CLASS_SET)
end

function mod.get_shared_option(key)
	-- Removed controls always use authored defaults, including old saved settings.
	if key == "hide_body" or key == "jiggle" then return true end
	if string.sub(key, 1, 7) == "jiggle_" then return nil end
	if key == "model_enabled" then
		return mod:get("model_enabled")
	end
	if key == "target_archetype" then
		return nil
	end
	return mod:get(key)
end

local function notify_providers(setting_id)
	local registry = get_mod("ModelReplacementRegistry")
	local api = registry and registry.api
	if api and api.version == 2 then
		api.changed()
	end

	for _, provider_id in ipairs(PROVIDERS) do
		local provider = get_mod(provider_id)
		if provider and provider.apply_shared_settings then
			local ok, err = pcall(provider.apply_shared_settings, setting_id or "model_selection")
			if not ok then
				mod:error("Could not refresh %s: %s", provider_id, tostring(err))
			end
		end
	end
end

local function update_model_options_target(setting_id)
	local class_name = string.sub(setting_id, 7)
	if not CLASS_SET[class_name] then
		return
	end

	local assigned = mod.model_for_class(class_name)
	if assigned ~= "none" then
		if mod:get("model_options_model") ~= assigned then
			mod:set("model_options_model", assigned, true)
		end
		return
	end

	local current = mod:get("model_options_model")
	if current ~= "none" and mod.is_model_selected(current) then
		return
	end
	for _, candidate_class in ipairs(CLASSES) do
		local candidate = mod.model_for_class(candidate_class)
		if candidate ~= "none" then
			mod:set("model_options_model", candidate, true)
			return
		end
	end
	mod:set("model_options_model", "none", true)
end

mod.toggle_models = function()
	local enabled = mod:get("model_enabled") == false
	mod:set("model_enabled", enabled, true)
	mod:echo("Model replacements %s", enabled and "on" or "off")
end

mod.switch_model = function()
	local variant = mod:get("model_variant") == "blue" and "red" or "blue"
	mod:set("model_variant", variant, true)
end

mod:command("anime_models", "Toggle all anime model replacements", mod.toggle_models)

mod.on_setting_changed = function(setting_id)
	update_model_options_target(setting_id)
	notify_providers(setting_id)
end

mod.on_enabled = function()
	notify_providers("model_enabled")
end

mod.on_disabled = function()
	preview_lifecycle.reset()
	screenshot_portraits.suspend()
	notify_providers("model_enabled")
end

mod.on_all_mods_loaded = function()
	notify_providers("model_selection")
end

mod.on_unload = function()
	preview_lifecycle.reset()
	screenshot_portraits.shutdown()
	local registry = get_mod("ModelReplacementRegistry")
	local api = registry and registry.api
	if api and api.version == 2 then
		api.changed()
	end
end
