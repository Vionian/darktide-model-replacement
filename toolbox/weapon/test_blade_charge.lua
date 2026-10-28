local root=arg[1]
local path=root..'/WeaponModelReplacement/scripts/mods/WeaponModelReplacement/'
local values={aura_size=2.5,aura_two_size=1.5,charge_two_size=1.5}
local mod={get=function(_,k)return values[k]end}
local colors={rgb=function()return .16,.67,1 end,number=function(_,k,default,low,high)
    local n=values[k] or default;return math.max(low,math.min(high,n))end}
Vector3=function(x,y,z)return {x,y,z}end
local writes={}
local indices,names={},{}
World={find_particles_variable=function(_,_,key)
        if not indices[key] then local i=#names+1;indices[key]=i;names[i]=key end
        return indices[key]end,
    set_particles_variable=function(_,_,key,value)writes[names[key]]=value end,
    has_particles_material=function()return false end}
local controls=dofile(path..'particle_controls.lua')
local charge=dofile(path..'charge.lua')
local count=0
for _,resource in ipairs({charge.resource,charge.wolf_resource})do
    for _,tier in ipairs({0,1,3})do
        local binding={component={num_special_charges=tier,special_active=true}}
        local brightness,volume=charge.factors(binding,mod,colors,'aura')
        controls.aura({},1,resource,mod,colors,.025*brightness,volume)
        assert(writes.energy_size[1]==1 and writes.energy_size[2]==1 and writes.energy_size[3]==1)
        assert(writes.energy_rgb[3]>writes.energy_rgb[2] and writes.energy_rgb[2]>writes.energy_rgb[1])
        count=count+1
    end
end
for _,resource in ipairs({charge.resource,charge.wolf_resource})do
    values.aura_size=.25;controls.aura({},1,resource,mod,colors,.025,1)
    assert(writes.energy_size[1]==.25);count=count+1
end
print('BLADE_CHARGE_TESTS_OK '..count)
