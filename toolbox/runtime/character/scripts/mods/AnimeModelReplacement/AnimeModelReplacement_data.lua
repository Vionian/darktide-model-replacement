local mod = get_mod("AnimeModelReplacement")
local definitions = mod:io_dofile("AnimeModelReplacement/scripts/mods/AnimeModelReplacement/model_definitions")
local costumes = mod:io_dofile("AnimeModelReplacement/scripts/mods/AnimeModelReplacement/costume_catalog")
local classes, widgets, models = {}, {}, {}
local function model_options()
    -- DMF localizes option.text in place. Never share option tables between widgets.
    local result = {}
    for _, model in ipairs(definitions.models) do
        result[#result+1] = {text=model.title,value=model.id}
    end
    return result
end
for _, class in ipairs(definitions.classes) do
    classes[#classes+1]={setting_id="model_"..class.id,title=class.title,type="dropdown",
        default_value=class.default_model,options=model_options()}
end
for _, model in ipairs(definitions.models) do
    local shown={}
    if model.id=="DaniyaReplacement" then
        widgets[#widgets+1]={setting_id="model_variant",type="dropdown",default_value="red",
            options={{text="variant_red",value="red"},{text="variant_blue",value="blue"}}}
        shown={#widgets}
    elseif costumes[model.id] then
        local catalog=costumes[model.id]
        local choices, variants = {}, {}
        for _, entry in ipairs(catalog.outfits) do
            local option={text=entry.title,value=entry.id,show_widgets={}}
            if entry.variants>1 then
                local colors={}
                for i=1,entry.variants do colors[#colors+1]={text="skin_variant_"..i,value=i} end
                variants[#variants+1]={setting_id=entry.asset.."_variant",title="skin_variation",
                    type="dropdown",default_value=1,options=colors}
                option.show_widgets={#variants}
            end
            choices[#choices+1]=option
        end
        if #choices > 1 then
            widgets[#widgets+1]={setting_id=catalog.setting,title="skin_outfit",type="dropdown",
                default_value="original",options=choices,sub_widgets=variants}
            shown={#widgets}
        else
            -- DMF rejects dropdowns with fewer than two choices. A single outfit has no
            -- selectable setting; keep any independent variant controls visible instead.
            for _, variant_widget in ipairs(variants) do
                widgets[#widgets+1]=variant_widget
                shown[#shown+1]=#widgets
            end
        end
    end
    models[#models+1]={text=model.title,value=model.id,show_widgets=shown}
end
return {name=mod:localize("mod_name"),description=mod:localize("mod_description"),is_togglable=true,
 options={widgets={
    {setting_id="class_models",type="group",sub_widgets=classes},
    {setting_id="common_settings",type="group",sub_widgets={
        {setting_id="model_enabled",type="checkbox",default_value=true},
        {setting_id="replace_teammates",type="checkbox",default_value=true},
        {setting_id="first_person_arms",type="checkbox",default_value=true},
        {setting_id="menu_previews",type="checkbox",default_value=true}}},
    {setting_id="model_options_model",type="dropdown",default_value="RoshiaReplacement",
        options=models,sub_widgets=widgets}}}}
