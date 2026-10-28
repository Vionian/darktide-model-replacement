"""Production equipment adapter + visibility helper regression (LuaJIT).

Engine parenting/recursive visibility are mocked; this is not a game render.
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/model-work/python-deps'))
from lupa.luajit21 import LuaRuntime


def audit(root=ROOT):
    report = []
    for path in sorted((root / 'scripts/mods').glob('*/weapon_links.lua')):
        lua = LuaRuntime(unpack_returned_tuples=True)
        config = next(path.parent.glob('*_proportion_bones.lua'))
        settings = lua.execute(config.read_text(encoding='utf-8-sig'))
        hands = [b for _, b in settings.body.bones.items() if 'hand' in b.name]
        assert len(hands) == 40, path
        native_hands = [b for b in hands if b.native_position_driver]
        source_distal = [b for b in hands if not b.native_position_driver]
        # Source-length profiles keep the middle/distal phalanges on local FK.
        # Wrist, palm, metacarpals and digit roots still use native contacts.
        assert all(settings.body.source_digit_lengths
                   and b.name.startswith(('j_lefthand', 'j_righthand'))
                   and b.name[-1:] in ('2', '3') and b.finger
                   and b.curl_gain == 1 and b.angle_limit == 180
                   for b in source_distal), path
        assert len(native_hands) in (20, 40), path
        arms_hands = [b for _, b in settings.arms.bones.items() if 'hand' in b.name]
        assert len(arms_hands) == 40 and all(b.native_position_driver for b in arms_hands), path
        lua.execute('''
          operations={}
          Unit={alive=function(u)return u and u.alive end,
                has_node=function()return true end,node=function()return 2 end}
          local function detach(u)
            if u.parent then u.parent.children[u]=nil end
            u.parent=nil
          end
          function attach(u,p)
            detach(u);u.parent=p;p.children[u]=true
          end
          function new_unit(parent)
            local u={alive=true,visible=true,children={}}
            if parent then attach(u,parent)end
            return u
          end
          Unit.set_unit_visibility=function(u,v,recursive)
            u.visible=v
            if recursive then
              for child in pairs(u.children)do Unit.set_unit_visibility(child,v,true)end
            end
          end
          World={LINK_MODE_NODE_NAME=1,LINK_MODE_NONE=0,
            unlink_unit=function(w,u)operations[#operations+1]='unlink';detach(u)end,
            link_unit=function(w,u,n,p)operations[#operations+1]='link';attach(u,p)end}
          function require()return {slot_configuration={
            slot_primary={slot_type='weapon'},slot_secondary={slot_type='weapon'},
            slot_combat_ability={slot_type='ability'},slot_pocketable={slot_type='pocketable'},
            slot_device={slot_type='device'},slot_body_torso={slot_type='body'}}}end
          function fresh()
            actor=new_unit();model=new_unit();world={};owner={}
            weapon=new_unit(actor);replacement=new_unit(actor)
            first_person=new_unit();weapon_1p=new_unit(first_person)
            slot={parent_unit_3p=actor,unit_3p=weapon,unit_1p=weapon_1p,
              item={attach_node='j_righthand'}}
            operations={}
          end
          controller={info=function()end}
          function get_mod()return controller end
          Managers={ui={view_active=function()return false end}}
          ScriptUnit={has_extension=function()return nil end}
          fresh()
        ''')
        module = lua.execute(path.read_text(encoding='utf-8-sig'))
        lua.globals().links = module
        lua.globals().lifecycle = lua.execute((root / 'scripts/mods/AnimeModelReplacement/preview_lifecycle.lua').read_text(encoding='utf-8-sig'))
        lua.execute('''
          links.update(owner,world,actor,model,{slot_primary=slot},true)
          -- Equipment can retire a still-alive old unit after replacing its slot.
          slot.unit_3p=replacement
          links.release(owner)
        ''')
        # Lua table proxies have no identity equality in Python.
        old_orphan = bool(lua.eval('weapon.parent~=actor'))
        retirement_operations = len(lua.globals().operations)
        lua.execute('''
          fresh()
          baton=weapon;shield=new_unit(baton)
          Unit.set_unit_visibility(baton,false,true) -- Native holster policy.
          -- Actual provider order: reveal cosmetic body, then equipment adapter.
          lifecycle.actor_subject(model,actor,true)
          links.update(owner,world,actor,model,{slot_secondary=slot},true)
          lifecycle.actor_subject(model,actor,true) -- Next frame's body refresh.
          hidden_equipment_revealed=baton.visible or shield.visible
          links.release(owner)
        ''')
        ghost = bool(lua.globals().hidden_equipment_revealed)
        if retirement_operations:
            report.append({'provider': path.parent.name, 'manual_link_operations': retirement_operations,
                           'retired_weapon_orphan': old_orphan, 'hidden_shield_baton_revealed': ghost})
            continue
        assert not old_orphan and not ghost, path
        lua.execute('''
          fresh()
          local slots={}
          for _,name in ipairs({'slot_primary','slot_secondary','slot_combat_ability',
            'slot_pocketable','slot_device','slot_body_torso'})do
            slots[name]={parent_unit_3p=actor,unit_3p=new_unit(actor),unit_1p=new_unit(first_person),
              item={attach_node='j_lefthand',breed_attach_node={human='j_righthand'},
                link_map_mode='LINK_MODE_NONE'},breed_name='human'}
          end
          for i=1,60 do
              -- Streaming may replace the slot while its old unit awaits deletion.
              local old=slot.unit_3p;slot.unit_3p=new_unit(actor)
              slots.slot_secondary=slot
              links.update(owner,world,actor,model,slots,true)
              lifecycle.actor_subject(model,actor,true)
              assert(old.parent==actor and slot.unit_3p.parent==actor)
              links.update(owner,world,actor,model,{slot_primary=slot},false)
              links.release(owner)
              assert(weapon.parent==actor and replacement.parent==actor)
              for _,s in pairs(slots)do
                assert(s.unit_3p.parent==actor and s.unit_1p.parent==first_person)
              end
          end
          -- Queued model deletion, lost world, model switches and dead drivers.
          links.update(owner,nil,actor,model,slots,true)
          model.alive=false;links.update(owner,world,actor,model,slots,true)
          actor.alive=false;model.alive=false;links.release(owner)
          assert(#operations==0,'Adapter reparented native equipment')
        ''')
        report.append({'provider': path.parent.name, 'native_hand_drivers': len(native_hands),
                       'source_length_distal_fingers': len(source_distal),
                       'first_person_native_hand_drivers': len(arms_hands),
                       'manual_link_operations': 0, 'retired_weapon_orphan': False,
                       'hidden_shield_baton_revealed': False, 'streaming_replacements': 60,
                       'weapon_ability_device_pocketable_slots_untouched': True,
                       'first_person_equipment_untouched': True, 'in_game_validation': False})
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=pathlib.Path, default=ROOT)
    parser.add_argument('--expect-old-orphan', action='store_true')
    parser.add_argument('--output', type=pathlib.Path)
    args = parser.parse_args()
    rows = audit(args.root)
    old = args.expect_old_orphan
    assert rows
    assert all(r['manual_link_operations'] > 0 and r['retired_weapon_orphan'] and r['hidden_shield_baton_revealed'] for r in rows) if old else all(r['manual_link_operations'] == 0 for r in rows), rows
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print('NATIVE_EQUIPMENT_LIFECYCLE', len(rows), 'old orphan reproduced' if old else 'passed')
