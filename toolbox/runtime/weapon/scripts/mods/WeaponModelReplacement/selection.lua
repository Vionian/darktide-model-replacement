local mod = get_mod('WeaponModelReplacement')
local S = {asset='WeaponModelReplacement:khravengger'}
S.profiles = {
    khravengger_force = {id='khravengger', default='khravengger', setting='skin_psyker_forcesword_2h', unit='content/mods/weapon_model_replacement/khravengger', prefix='content/weapons/player/melee/2h_force_sword/attachments/', templates={forcesword_2h_p1_m1=true,forcesword_2h_p1_m2=true}, effects=true, cover=true, material='khravengger_pbr'},
    -- Langzhifei is the ordinary one-handed Psyker force sword.  It has a
    -- separate setting so selecting it can never change the two-handed
    -- Blaze Force Greatsword profile above.
    langzhifei_force = {id='langzhifei', default='langzhifei', setting='skin_psyker_forcesword_1h', unit='content/mods/weapon_model_replacement/langzhifei', prefix='content/weapons/player/melee/force_sword/attachments/', templates={forcesword_p1_m1=true,forcesword_p1_m2=true,forcesword_p1_m3=true}, material='langzhifei_material_0',effects=true,cover=true,palette='wolf'},
    khravengger_power = {id='khravengger', setting='skin_zealot_relicsword_2h', unit='content/mods/weapon_model_replacement/khravengger', prefix='content/weapons/player/melee/2h_power_sword/attachments/', templates={powersword_2h_p1_m1=true,powersword_2h_p1_m2=true}, cover=true, material='khravengger_pbr'},
}
local function name(value)
    if type(value) == 'string' then return value end
    if type(value) ~= 'table' then return nil end
    local master = value.__master_item
    return value.name or (type(master) == 'table' and master.name)
end
function S.matches(item, scope)
    if type(item) ~= 'table' then return false end
    local template = item.weapon_progression_template or item.weapon_template
    if not template then
        local item_name = name(item)
        template = item_name and item_name:match('^content/items/weapons/player/melee/([^/]+)$')
    end
    for _, profile in pairs(S.profiles) do
        if profile.templates[template] and (mod:get(profile.setting) == profile.id or (mod:get(profile.setting)==nil and profile.default==profile.id)) then
            return scope ~= 'reference' or name(item.slot_weapon_skin) == profile.reference_skin
        end
    end
    return false
end
function S.family(item)
    if type(item) ~= 'table' then return nil end
    local template = item.weapon_progression_template or item.weapon_template
    if not template then local item_name=name(item); template=item_name and item_name:match('/([^/]+)$') end
    for _, profile in pairs(S.profiles) do
        if profile.templates[template] then return profile end
    end
end
function S.profile(item)
    local profile = S.family(item)
    if profile and (mod:get(profile.setting) == profile.id or (mod:get(profile.setting)==nil and profile.default==profile.id)) then return profile end
end
function S.part_kind(path)
    if type(path) ~= 'string' then return nil end
    local prefix
    for _,profile in pairs(S.profiles) do if path:sub(1,#profile.prefix)==profile.prefix then prefix=profile.prefix;break end end
    if not prefix then return nil end
    local part = path:sub(#prefix + 1):match('^([^/]+)')
    if not part then return nil end
    for _, kind in ipairs({'grip', 'hilt', 'blade', 'pommel'}) do
        if part:match('^' .. kind .. '_') then return kind end
    end
end
return S
