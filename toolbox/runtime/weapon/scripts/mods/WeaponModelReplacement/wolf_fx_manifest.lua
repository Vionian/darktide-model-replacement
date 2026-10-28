local source=get_mod('WeaponModelReplacement'):io_dofile('WeaponModelReplacement/scripts/mods/WeaponModelReplacement/fx_manifest')
local keep={force_sword_impact_02=true,generic_shove_warp_01=true,psyker_block=true,psyker_parry=true,
    psyker_push=true,psyker_block_impact_01=true,psyker_venting=true,
    force_staff_channel_charge=true,force_staff_channel_charge_husk=true}
local result={}
for native,entry in pairs(source) do
    local short=entry.resource:match('/ice_(.+)$')
    if keep[short] then result[native]={resource='content/mods/weapon_model_replacement/violet_'..short,
        group=entry.group,materials=entry.materials} end
end
-- The ordinary sword's side-key action spawns this before special_active.
-- Reuse our private blue-violet channel swirl; the native action owns its stop.
local channel=result['content/fx/particles/weapons/force_staff/force_staff_channel_charge']
result['content/fx/particles/weapons/swords/forcesword/psyker_activate_forcesword']=channel
return result
