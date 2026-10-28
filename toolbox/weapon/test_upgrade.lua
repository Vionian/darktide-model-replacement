local root=assert(arg[1])
local path=root..'/WeaponModelReplacement/scripts/mods/WeaponModelReplacement/'
local total=0
local function check(name,fn) fn();total=total+1;print('PASS '..name) end
local values,hooks,safe={}, {}, {}
local localization=dofile(path..'WeaponModelReplacement_localization.lua')
local mod={}
function mod:get(key) return values[key] end
function mod:set(key,value) values[key]=value end
function mod:is_enabled() return values.enabled~=false end
function mod:localize(key,...)
    assert(localization[key],'missing localization '..key)
    return localization[key]['zh-cn']
end
function mod:io_dofile(p) return dofile(root..'/'..p..'.lua') end
function mod:hook(target,name,fn) hooks[target]=hooks[target] or {};assert(not hooks[target][name]);hooks[target][name]=fn end
function mod:hook_safe(target,name,fn) safe[target]=safe[target] or {};assert(not safe[target][name]);safe[target][name]=fn end
function mod:warning(...) end
function mod:echo(...) end
local dmf={settings={},get=function(self,k)return self.settings[k] end,set=function(self,k,v)self.settings[k]=v end}
function dmf:dump(...)end
function dmf.throw_error(...)error(string.format(...))end
function dmf.quick_localize(owner,k) if localization[k] then return owner:localize(k) end end
function dmf.mod_has_settings()return true end
function mod:get_name()return 'WeaponModelReplacement'end
function mod:get_readable_name()return self:localize('mod_name')end
function mod:get_description()return self:localize('mod_description')end
function mod:get_metadata(k)return 'test'end
function mod:get_internal_data(k)return true end
function get_mod(name) if name=='DMF' then return dmf else return mod end end
local data=dofile(path..'WeaponModelReplacement_data.lua')
check('six class sections and no Ogryn',function()
    assert(#data.options.widgets==6)
    local expected={'veteran','zealot','psyker','adamant','broker','cryptic'}
    for i,id in ipairs(expected) do assert(data.options.widgets[i].setting_id=='class_'..id) end
end)
check('Psyker one-handed and two-handed swords have separate skin dropdowns',function()
    local one=data.options.widgets[3].sub_widgets[1]
    assert(one.title=='weapon_forcesword_1h' and one.setting_id=='skin_psyker_forcesword_1h')
    assert(one.default_value=='langzhifei' and one.options[1].value=='none' and one.options[2].value=='langzhifei')
    local w=data.options.widgets[3].sub_widgets[2]
    assert(w.title=='weapon_forcesword_2h' and w.type=='dropdown')
    assert(w.default_value=='khravengger' and w.options[1].value=='none' and w.options[2].value=='khravengger')
    local zealot=data.options.widgets[2].sub_widgets[1]
    assert(zealot.title=='weapon_relicsword_2h' and zealot.default_value=='none' and zealot.options[2].value=='khravengger')
end)
check('installed DMF accepts every widget',function()
    dofile('<DARKTIDE_GAME>/mods/dmf/scripts/mods/dmf/modules/core/options.lua')
    dmf.initialize_mod_options(mod,data.options)
    assert(#dmf.options_widgets_data==1 and values.fp_height_cm==3 and values.ice_effects==true)
end)
check('menu placement is immediately after anime and idempotent',function()
    local order=dofile(path..'menu_order.lua')
    local a={{{mod_name='Other'}},{{mod_name='WeaponModelReplacement'}},{{mod_name='AnimeModelReplacement'}},{{mod_name='Last'}}}
    order.reorder(a);order.reorder(a)
    assert(a[2][1].mod_name=='AnimeModelReplacement' and a[3][1].mod_name=='WeaponModelReplacement' and #a==4)
end)
local mt={}
mt.__add=function(a,b)return setmetatable({a[1]+b[1],a[2]+b[2],a[3]+b[3]},mt)end
mt.__sub=function(a,b)return setmetatable({a[1]-b[1],a[2]-b[2],a[3]-b[3]},mt)end
Vector3=setmetatable({length=function(v)return math.sqrt(v[1]^2+v[2]^2+v[3]^2)end,zero=function()return setmetatable({0,0,0},mt)end},{__call=function(_,x,y,z)return setmetatable({x,y,z},mt)end})
function Vector3Box(v)return {unbox=function()return Vector3(v[1],v[2],v[3])end}end
Quaternion={rotate=function(_,v)return v end}
Matrix4x4={identity=function()return {}end,from_translation=function(v)return {translation=v}end}
Unit={alive=function(u)assert(not u.world or not u.world.dead,'dead world access');return u.alive~=false end,
    local_rotation=function()return {}end,local_position=function(u)return u.position end,
    set_local_position=function(u,_,v)u.position=v end,
    set_mesh_visibility=function(u,name,visible)u.meshes=u.meshes or {};u.meshes[name]=visible end,
    set_scalar_for_material=function(u,material,key,value)u.materials=u.materials or {};u.materials[material]=u.materials[material] or {};u.materials[material][key]=value end,
    set_local_scale=function(u,node,value)u.scales=u.scales or {};u.scales[node]=value end,
    node=function(_,name)assert(name:match('^cover_[rgb]_mesh$'),'unexpected Unit.node '..name);return name end}
World={update_unit_and_children=function(w,u)u.updated=(u.updated or 0)+1 end,time=function()return 1 end}
local weapon,unit={}, {position=Vector3(1,2,3)}
local loadout={_inventory_component={wielded_slot='slot_primary'},_equipment={slot_primary={unit_1p=weapon}}}
ScriptUnit={has_extension=function(u)return u.loadout end}
local extension={_is_local_unit=true,_unit={loadout=loadout},_world={},_first_person_unit=unit,is_in_first_person_mode=function()return true end}
local rig=dofile(path..'viewmodel.lua').install(mod,function(root)return root==weapon end)
local height=safe.PlayerUnitFirstPersonExtension.update_unit_position
check('height moves complete FP root exactly 3 cm after native placement',function()height(extension,unit,.016,1);assert(math.abs(unit.position[3]-3.03)<1e-8 and unit.position[1]==1)end)
check('duplicate position callbacks in one frame do not accumulate',function()height(extension,unit,.016,1);assert(math.abs(unit.position[3]-3.03)<1e-8)end)
check('native placement each frame receives the selected offset',function()for frame=2,101 do unit.position=Vector3(1,2,3);height(extension,unit,.016,frame);assert(math.abs(unit.position[3]-3.03)<1e-8)end end)
check('disable restore removes only owned offset',function()rig.restore();assert(math.abs(unit.position[3]-3)<1e-8);rig.restore()end)
check('nonselected weapon and zero height preserve pose',function()
    loadout._equipment.slot_primary.unit_1p={};height(extension);assert(unit.position[3]==3)
    loadout._equipment.slot_primary.unit_1p=weapon;values.fp_height_cm=0;height(extension);assert(unit.position[3]==3);values.fp_height_cm=3
end)
check('restore does not clobber newer native pose',function()height(extension);unit.position=Vector3(1,2,4);rig.restore();assert(unit.position[3]==4)end)
check('height upper bound and remote player exclusion',function()
    values.fp_height_cm=100;unit.position=Vector3(0,0,0);height(extension);assert(unit.position[3]==.08);rig.restore()
    extension._is_local_unit=false;height(extension);assert(unit.position[3]==0);extension._is_local_unit=true;values.fp_height_cm=3
end)
local world={};Managers={world={_worlds={world},_disabled_worlds={}},state={}}
GameParameters={destroy_unmanaged_particles=true}
local rootunit,visual={world=world},{world=world}
local item={weapon_template='forcesword_2h_p1_m1'}
local sel=dofile(path..'selection.lua')
local records={[rootunit]={root=rootunit,visual=visual,originals={},world=world,first_person=true,
    profile=sel.profile({weapon_template='forcesword_2h_p1_m1'})}}
local selected=function(i)return sel.matches(i)end
local fx=dofile(path..'ice_effects.lua').install(mod,sel,records,function()return true end,selected)
local live,next_id={},0
function World.are_particles_playing(w,id)assert(not w.dead);return live[id]~=nil end
function World.find_particles_variable(w,name,key)return 1 end
function World.set_particles_variable(w,id,index,value)assert(live[id]);live[id].writes=(live[id].writes or 0)+1 end
function World.has_particles_material()return false end
function World.set_particles_use_custom_fov(w,id,value)live[id].fov=value end
local function create(w,name,...)next_id=next_id+1;live[next_id]={name=name};return next_id end
local function destroy(w,id)live[id]=nil end
World.destroy_particles=function(w,id)return hooks[World].destroy_particles(destroy,w,id)end
World.create_particles=function(w,name,...)return hooks[World].create_particles(create,w,name,...)end
World.link_particles=function(w,id,u,node,pose,policy)
    return hooks[World].link_particles(function(w,id,u,node,pose)live[id].unit=u;live[id].pose=pose end,w,id,u,node,pose,policy)
end
local native='content/fx/particles/weapons/foce_sword/forcesword_2h_stage2'
local ownerloadout={_inventory_component={wielded_slot='slot_primary'},_equipment={slot_primary={unit_1p=rootunit,item=item}}}
local extensionfx={_visual_loadout_extension=ownerloadout}
local wrapper=hooks.PlayerUnitFxExtension._create_particles_wrapper
check('target rendering uses private ice resource',function()
    local id=wrapper(function()return World.create_particles(world,native)end,extensionfx)
    assert(live[id].name=='content/mods/weapon_model_replacement/ice_forcesword_2h_stage2')
end)
check('unrelated particles keep native names',function()local id=World.create_particles(world,native);assert(live[id].name==native)end)
check('context errors restore native context',function()pcall(wrapper,function()error('expected')end,extensionfx);local id=World.create_particles(world,native);assert(live[id].name==native)end)
check('particle group fallback requires target owner',function()
    local actor={world=world,loadout=ownerloadout}
    Managers.state.extension={system=function()return {_world=world,unit_to_particle_group_lookup={[actor]=42}}end}
    local id=World.create_particles(world,native,Vector3.zero(),nil,nil,42);assert(live[id].name:match('/ice_'))
end)
check('sword-bound stage links to custom blade with weapon FOV',function()
    local id=wrapper(function()return World.create_particles(world,native)end,extensionfx)
    World.link_particles(world,id,rootunit,1,{},'destroy');assert(live[id].unit==visual and live[id].fov==true)
end)
check('impact remapping preserves shared template and return tuples',function()
    local template={vfx={{effects={native}}}};local actor={world=world,loadout=ownerloadout}
    local a,b,c=hooks.FxSystem.play_impact_fx(function(self,fx)assert(fx~=template);assert(fx.vfx[1].effects[1]:match('/ice_'));return 1,nil,3 end,{},template,nil,nil,nil,actor,{})
    assert(a==1 and b==nil and c==3 and template.vfx[1].effects[1]==native)
end)
check('turning ice off restores native creation immediately',function()values.ice_effects=false;fx.settings_changed();local id=wrapper(function()return World.create_particles(world,native)end,extensionfx);assert(live[id].name==native);values.ice_effects=true end)
check('particle id reuse clears stale ownership',function()
    next_id=100;local id=wrapper(function()return World.create_particles(world,native)end,extensionfx);assert(id==101)
    next_id=100;World.create_particles(world,'unrelated');World.link_particles(world,101,rootunit,1,{},'destroy');assert(live[101].unit==rootunit)
end)
local component={num_special_charges=0,special_active=false}
local firstmode=true
local controller={_world=world,_slot_name='slot_primary',_inventory_slot_component=component,
    _visual_loadout_extension=ownerloadout,_first_person_extension={is_in_first_person_mode=function()return firstmode end}}
local function aura_count()local n=0;for _,p in pairs(live)do if p.name=='content/mods/weapon_model_replacement/ice_charge_aura' then n=n+1 end end;return n end
check('native charge thresholds create aura only when charged',function()
    safe.ForceWeaponEffects.init(controller,{world=world},nil,{weapon_special_tweak_data={thresholds={{name='middle',threshold=10},{name='high',threshold=20}}}},nil,item,rootunit,nil)
    fx.update(.01);assert(aura_count()==0)
    component.num_special_charges=10;fx.update(.01);assert(aura_count()==1 and records[rootunit].aura_id)
    assert(records[rootunit].cover_active and visual.meshes.cover_b_mesh_p0 and visual.meshes.cover_g_mesh_p0 and visual.meshes.cover_r_mesh_p0)
    assert(visual.materials.ice_cover_b.intensity>visual.materials.ice_cover_g.intensity
        and visual.materials.ice_cover_g.intensity>visual.materials.ice_cover_r.intensity)
end)
check('charged second tier updates existing aura without respawning',function()
    local id=records[rootunit].aura_id;component.num_special_charges=20;fx.update(.01)
    assert(records[rootunit].aura_id==id and aura_count()==1 and live[id].writes>0)
    assert(visual.scales.cover_b_mesh[1]==1 and visual.scales.cover_b_mesh[2]==1)
end)
check('Zealot PowerWeaponEffects-only binding drives its cover layer',function()
    values.skin_zealot_relicsword_2h='khravengger'
    local zealot_root,zealot_visual={world=world},{world=world,position=Vector3.zero()}
    records[zealot_root]={root=zealot_root,visual=zealot_visual,originals={},world=world,first_person=true,
        profile=sel.profile({weapon_template='powersword_2h_p1_m1'})}
    local zealot_component={num_special_charges=0,special_active=true}
    local zealot_controller={_world=world,_slot_name='slot_primary',_inventory_slot_component=zealot_component,
        _first_person_extension={is_in_first_person_mode=function()return true end}}
    safe.PowerWeaponEffects.init(zealot_controller,{world=world,visual_loadout_extension=ownerloadout},
        {name='slot_primary',unit_1p=zealot_root},
        {weapon_special_tweak_data={thresholds={}}},nil,{weapon_template='powersword_2h_p1_m1'},nil,nil)
    fx.update(.01)
    assert(records[zealot_root].cover_active and zealot_visual.meshes.cover_b_mesh_p0)
end)
check('unwield and camera switch remove attached aura',function()
    ownerloadout._inventory_component.wielded_slot='slot_secondary';fx.update(.01);assert(aura_count()==0)
    ownerloadout._inventory_component.wielded_slot='slot_primary';firstmode=false;fx.update(.01);assert(aura_count()==0)
    firstmode=true;fx.update(.01);assert(aura_count()==1)
end)
check('aura id reuse cannot destroy another effect',function()
    local id=records[rootunit].aura_id;next_id=id-1;World.create_particles(world,'unrelated')
    assert(records[rootunit].aura_id==nil);fx.retire(records[rootunit]);assert(live[id].name=='unrelated')
end)
check('native controller destroy stops owned charge aura',function()
    fx.update(.01);assert(aura_count()==1);safe.ForceWeaponEffects.destroy(controller);assert(aura_count()==0)
end)
values.skin_psyker_forcesword_1h='langzhifei'
local wolfitem={weapon_template='forcesword_p1_m1'}
local wolfroot,wolfvisual={world=world},{world=world}
local wolfthird,wolfthirdvisual={world=world},{world=world}
local wolfprofile=sel.profile(wolfitem)
records[wolfroot]={root=wolfroot,visual=wolfvisual,originals={},world=world,first_person=true,profile=wolfprofile}
records[wolfthird]={root=wolfthird,visual=wolfthirdvisual,originals={},world=world,first_person=false,profile=wolfprofile}
local wolfloadout={_inventory_component={wielded_slot='slot_primary'},_equipment={slot_primary={unit_1p=wolfroot,unit_3p=wolfthird,item=wolfitem}}}
local wolfextension={_visual_loadout_extension=wolfloadout}
local wolfcomponent={num_special_charges=0,special_active=false}
local wolfmode=true
local wolfcontroller={_world=world,_slot_name='slot_primary',_inventory_slot_component=wolfcomponent,
    _visual_loadout_extension=wolfloadout,_first_person_extension={is_in_first_person_mode=function()return wolfmode end}}
safe.ForceWeaponEffects.init(wolfcontroller,{world=world,visual_loadout_extension=wolfloadout},
    {name='slot_primary',unit_1p=wolfroot,unit_3p=wolfthird},{},nil,wolfitem,{world=world},{world=world})
local nativehit='content/fx/particles/impacts/weapons/force_sword/force_sword_impact_02'
local function wolf_aura_count()
    local count=0;for _,p in pairs(live)do if p.name=='content/mods/weapon_model_replacement/violet_charge_aura' then count=count+1 end end;return count
end
check('ordinary wolf profile enables its own palette and serialized cover',function()
    assert(wolfprofile.palette=='wolf' and wolfprofile.cover and wolfprofile.effects)
    for _,mark in ipairs({'forcesword_p1_m1','forcesword_p1_m2','forcesword_p1_m3'})do assert(sel.profile({weapon_template=mark})==wolfprofile)end
end)
check('wolf palette does not change greatsword ice selection',function()
    assert(sel.profile(item).palette==nil and sel.profile(item).id=='khravengger')
end)
local nativeactivate='content/fx/particles/weapons/swords/forcesword/psyker_activate_forcesword'
check('side-key windup uses violet before special_active becomes true',function()
    assert(wolfcomponent.special_active==false)
    local id=wrapper(function()return World.create_particles(world,nativeactivate)end,wolfextension)
    assert(live[id].name=='content/mods/weapon_model_replacement/violet_force_staff_channel_charge')
    World.destroy_particles(world,id);assert(not live[id])
end)
check('ordinary sword channel and husk effects use private violet resources',function()
    for _,suffix in ipairs({'','_husk'})do
        local id=wrapper(function()return World.create_particles(world,'content/fx/particles/weapons/force_staff/force_staff_channel_charge'..suffix)end,wolfextension)
        assert(live[id].name=='content/mods/weapon_model_replacement/violet_force_staff_channel_charge'..suffix)
        World.destroy_particles(world,id)
    end
end)
check('original skin and unrelated actors keep the native activation effect',function()
    values.skin_psyker_forcesword_1h='none'
    local id=wrapper(function()return World.create_particles(world,nativeactivate)end,wolfextension)
    assert(live[id].name==nativeactivate);World.destroy_particles(world,id)
    values.skin_psyker_forcesword_1h='langzhifei'
    id=World.create_particles(world,nativeactivate)
    assert(live[id].name==nativeactivate);World.destroy_particles(world,id)
end)
check('ordinary wolf impacts use the private violet resource',function()
    local id=wrapper(function()return World.create_particles(world,nativehit)end,wolfextension)
    assert(live[id].name=='content/mods/weapon_model_replacement/violet_force_sword_impact_02')
end)
check('ordinary original appearance keeps native particle names',function()
    values.skin_psyker_forcesword_1h='none'
    local id=wrapper(function()return World.create_particles(world,nativehit)end,wolfextension)
    assert(live[id].name==nativehit);values.skin_psyker_forcesword_1h='langzhifei'
end)
check('uncharged wolf blade has no coating or charge aura',function()
    fx.update(.01);assert(wolf_aura_count()==0 and not records[wolfroot].cover_active)
end)
check('psyker peril alone cannot activate wolf charging',function()
    wolfcontroller._warp_charge_component={current_percentage=1};fx.update(.01);assert(wolf_aura_count()==0)
end)
check('side-key special_active charges wolf even with a zero charge counter',function()
    wolfcomponent.special_active=true;fx.update(.01)
    assert(wolf_aura_count()==1 and records[wolfroot].cover_active)
    assert(wolfvisual.materials.ice_cover_b.intensity>wolfvisual.materials.ice_cover_r.intensity
        and wolfvisual.materials.ice_cover_r.intensity>wolfvisual.materials.ice_cover_g.intensity)
    assert(live[records[wolfroot].aura_id].fov==true and live[records[wolfroot].aura_id].unit==wolfvisual)
end)
check('steady native wolf charge reuses its aura instead of stacking',function()
    local id=records[wolfroot].aura_id;for _=1,20 do fx.update(.01)end
    assert(wolf_aura_count()==1 and records[wolfroot].aura_id==id)
end)
check('wolf brightness scales its cover independently',function()
    local old=wolfvisual.materials.ice_cover_b.intensity
    values.wolf_fx_strength=.5;fx.settings_changed();fx.update(.01)
    assert(math.abs(wolfvisual.materials.ice_cover_b.intensity-old*.5)<1e-8)
    values.wolf_fx_strength=1;fx.settings_changed();fx.update(.01)
end)
check('disabling ice leaves violet wolf effects active',function()
    values.ice_effects=false;fx.settings_changed();fx.update(.01)
    assert(wolf_aura_count()==1 and records[wolfroot].cover_active)
    values.ice_effects=true;fx.settings_changed()
end)
check('disabling wolf effects removes aura and hides its coating',function()
    values.wolf_effects=false;fx.settings_changed();fx.update(.01)
    assert(wolf_aura_count()==0 and not records[wolfroot].cover_active)
end)
check('reenabling wolf effects restores a still-active native charge',function()
    values.wolf_effects=true;fx.settings_changed();fx.update(.01)
    assert(wolf_aura_count()==1 and records[wolfroot].cover_active)
end)
check('native charge expiry immediately clears wolf coating and aura',function()
    wolfcomponent.special_active=false;fx.update(.01)
    assert(wolf_aura_count()==0 and not records[wolfroot].cover_active)
end)
check('wolf camera switch uses one correctly flagged third-person aura',function()
    wolfcomponent.special_active=true;wolfmode=false;fx.update(.01)
    assert(wolf_aura_count()==1 and records[wolfroot].aura_id==nil)
    local id=records[wolfthird].aura_id;assert(id and live[id].fov==false and live[id].unit==wolfthirdvisual)
end)
check('unwielding wolf clears both perspective charge surfaces',function()
    wolfloadout._inventory_component.wielded_slot='slot_secondary';fx.update(.01)
    assert(wolf_aura_count()==0 and not records[wolfroot].cover_active and not records[wolfthird].cover_active)
end)
local dormantroot,dormantvisual={world=world},{world=world}
local dormantloadout={_inventory_component={wielded_slot='slot_primary'}}
local dormantcontroller={_inventory_slot_component={special_active=true,num_special_charges=0},
    _first_person_extension={is_in_first_person_mode=function()return true end}}
check('effect controllers initialized on original skins survive dropdown activation',function()
    values.skin_psyker_forcesword_1h='none'
    safe.ForceWeaponEffects.init(dormantcontroller,{world=world,visual_loadout_extension=dormantloadout},
        {name='slot_primary',unit_1p=dormantroot},{},nil,wolfitem,nil,nil)
    values.skin_psyker_forcesword_1h='langzhifei'
    records[dormantroot]={root=dormantroot,visual=dormantvisual,originals={},world=world,first_person=true,profile=wolfprofile}
    fx.update(.01);assert(records[dormantroot].cover_active and records[dormantroot].aura_id)
end)
check('wolf controller destruction releases its owned aura',function()
    safe.ForceWeaponEffects.destroy(dormantcontroller);safe.ForceWeaponEffects.destroy(wolfcontroller)
    assert(wolf_aura_count()==0)
end)
check('destroyed worlds never receive stale particle writes',function()fx.forget_world(world);Managers.world._worlds={};world.dead=true;fx.update(.1)end)
print('UPGRADE_TESTS_OK '..total)
