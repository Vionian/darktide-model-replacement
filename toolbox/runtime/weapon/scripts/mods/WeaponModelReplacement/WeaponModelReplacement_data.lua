local mod = get_mod('WeaponModelReplacement')
local catalog = mod:io_dofile('WeaponModelReplacement/scripts/mods/WeaponModelReplacement/catalog')
local widgets = {}
for _, class in ipairs(catalog.classes) do
    local weapons = {}
    for _, weapon in ipairs(class.weapons) do
        local options = {}
        for _, skin in ipairs(weapon.skins) do options[#options+1] = {text=skin.title,value=skin.id} end
        weapons[#weapons+1] = {setting_id=weapon.setting,title=weapon.title,tooltip=weapon.setting..'_tooltip',type='dropdown',
            default_value=weapon.default,options=options}
    end
    if #weapons == 0 then
        weapons[1] = {setting_id='empty_'..class.id,title='no_adapted_weapons',type='button',
            button_text='catalog_pending',function_name='wmr_no_models'}
    end
    if class.id == 'psyker' then
        weapons[#weapons+1] = {setting_id='wolf_settings',type='group',sub_widgets={
            {setting_id='wolf_effects',tooltip='wolf_effects_tooltip',type='checkbox',default_value=true},
            {setting_id='wolf_fx_strength',tooltip='wolf_fx_strength_tooltip',type='numeric',default_value=1,range={0,2},decimals_number=2},
        }}
        weapons[#weapons+1] = {setting_id='khravengger_settings',type='group',sub_widgets={
            {setting_id='fp_height_cm',tooltip='fp_height_cm_tooltip',type='numeric',default_value=3,range={0,8},decimals_number=1},
            {setting_id='ice_effects',tooltip='ice_effects_tooltip',type='checkbox',default_value=true},
            {setting_id='ice_fx_strength',tooltip='ice_fx_strength_tooltip',type='numeric',default_value=1,range={0,2},decimals_number=2},
            {setting_id='emission_strength',tooltip='emission_strength_tooltip',type='numeric',default_value=1,range={0,5},decimals_number=2},
        }}
    elseif class.id == 'zealot' then
        weapons[#weapons+1] = {setting_id='khravengger_zealot_settings',title='khravengger_zealot_settings',type='group',sub_widgets={
            {setting_id='fp_height_zealot_cm',title='fp_height_zealot_cm',tooltip='fp_height_cm_tooltip',type='numeric',default_value=3,range={0,8},decimals_number=1},
        }}
    end
    widgets[#widgets+1] = {setting_id='class_'..class.id,type='group',sub_widgets=weapons}
end
return {
    name = mod:localize('mod_name'),
    description = mod:localize('mod_description'),
    is_togglable = true,
    options = {widgets=widgets},
}
