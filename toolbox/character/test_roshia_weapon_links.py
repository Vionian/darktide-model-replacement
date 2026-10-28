"""Exercise actual equipment-link Lua with spawn/swap/despawn/1P transitions."""
import pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/model-work/python-deps'))
from lupa import LuaRuntime
lua=LuaRuntime()
lua.execute('''
World={LINK_MODE_NODE_NAME=1,LINK_MODE_NONE=0}
Unit={}
local links={}
Unit.alive=function(u)return u.alive~=false end
Unit.has_node=function(u,n)return u.nodes[n]~=nil end
Unit.node=function(u,n)return u.nodes[n]end
World.unlink_unit=function(w,u)u.link=nil end
World.link_unit=function(w,u,i,p,n,m)u.link={parent=p,node=n,mode=m};u.count=(u.count or 0)+1 end
require=function()return {slot_configuration={slot_primary={slot_type="weapon"},slot_secondary={slot_type="weapon"},
slot_body={slot_type="body"},slot_pocketable={slot_type="pocketable"}}}end
''')
lua.globals().module=lua.execute((ROOT/'scripts/mods/RoshiaReplacement/weapon_links.lua').read_text())
lua.execute('''
local actor={nodes={j_righthand=10,j_lefthand=20}}
local model={nodes={j_righthand=30,j_lefthand=40}}
local owner={}
local gun={nodes={}};local skin={nodes={}};local first_person={nodes={}}
local slot={item={attach_node="j_righthand"},unit_3p=gun,unit_1p=first_person,parent_unit_3p=actor}
local slots={slot_primary=slot,slot_body={item={},unit_3p=skin,parent_unit_3p=actor}}
module.update(owner,{},actor,model,slots,true)
assert(gun.link.parent==model and gun.link.node==30)
assert(not skin.link and not first_person.link)
local world={}
module.update(owner,world,actor,model,slots,true)
local count=gun.count
module.update(owner,world,actor,model,slots,true)
assert(gun.count==count)
module.update(owner,world,actor,model,slots,false)
assert(gun.link.parent==actor and gun.link.node==10)
module.update(owner,world,actor,model,slots,true)
local old=gun;gun={nodes={}};slot.unit_3p=gun;old.alive=false
module.update(owner,world,actor,model,slots,true)
assert(gun.link.parent==model)
module.release(owner)
assert(gun.link.parent==actor)
slot.item={breed_attach_node={human="j_lefthand"},attach_node="j_righthand",link_map_mode="LINK_MODE_NONE"}
slot.breed_name="human"
module.update(owner,world,actor,model,slots,true)
assert(gun.link.node==40 and gun.link.mode==0)
module.release(owner)
assert(gun.link.node==20 and gun.link.parent==actor)
slot.item.attach_node="missing";slot.item.breed_attach_node=nil
module.update(owner,world,actor,model,slots,true)
assert(gun.link.parent==actor)
module.release(owner)
''')
print('WEAPON_LINK_LIFECYCLE_OK')
