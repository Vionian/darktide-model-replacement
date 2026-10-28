local M = {}
function M.reorder(data)
    local own
    for i=#data,1,-1 do
        if data[i][1].mod_name=='WeaponModelReplacement' then own=table.remove(data,i);break end
    end
    if not own then return end
    for i,entry in ipairs(data) do
        if entry[1].mod_name=='AnimeModelReplacement' then table.insert(data,i+1,own);return end
    end
    data[#data+1]=own
end
function M.install(mod)
    local dmf=get_mod('DMF')
    if not dmf or type(dmf.create_mod_options_settings)~='function' then return end
    if dmf.options_widgets_data then M.reorder(dmf.options_widgets_data) end
    mod:hook(dmf,'create_mod_options_settings',function(func,self,...)
        if self.options_widgets_data then M.reorder(self.options_widgets_data) end
        return func(self,...)
    end)
end
return M
