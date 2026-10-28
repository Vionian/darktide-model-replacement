local mod = get_mod('__MOD_ID__')
local profile = {id='__ASSET_ID__',default='__ASSET_ID__',setting='skin_model',
    unit='content/mods/__ASSET_ID__/weapon',prefix='__ATTACHMENT_PREFIX__',templates={__TEMPLATE_MAP__}}
local S = {asset='__MOD_ID__:__ASSET_ID__',profiles={replacement=profile}}
local function family(item)
    if type(item) ~= 'table' then return nil end
    local template = item.weapon_progression_template or item.weapon_template
    if not template then
        local master = item.__master_item
        local name = item.name or (type(master)=='table' and master.name)
        template = name and name:match('/([^/]+)$')
    end
    return profile.templates[template] and profile or nil
end
S.family = family
function S.profile(item)
    local selected = mod:get('skin_model')
    return family(item) and (selected == nil or selected == profile.id) and profile or nil
end
function S.part_kind(path)
    if type(path) ~= 'string' or path:sub(1,#profile.prefix) ~= profile.prefix then return nil end
    local part = path:sub(#profile.prefix+1):match('^([^/]+)')
    for _, kind in ipairs({'grip','hilt','blade','pommel'}) do
        if part and part:match('^'..kind..'_') then return kind end
    end
end
return S
