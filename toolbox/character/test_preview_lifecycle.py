"""Exercise production provider hooks with reentrant preview teardown callbacks.

Engine calls are mocked; this checks Lua lifecycle and package requests, not pixels.
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/model-work/python-deps'))
from lupa.luajit21 import LuaRuntime


def exercise(root, provider, outfit="original"):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().provider_id = provider
    lua.globals().requested_outfit = outfit
    lua.globals().read_mod = lambda path: (root / (path.removeprefix('AnimeModelReplacement/') + '.lua')).read_text(encoding='utf-8-sig')
    lua.globals().asset_exists = lambda name: (root / 'Custom' / name.split(':')[-1] / 'build.json').is_file()
    lua.execute('''
        hooks={}; requests={}; units={}; active=true
        CLASS={UIProfileSpawner={},PlayerUnitVisualLoadoutExtension={},PlayerHuskVisualLoadoutExtension={}}
        Managers={}
        Unit={alive=function(u)return u and u.alive end,
              world_pose=function()return {}end,
              set_unit_culling=function()end,
              set_unit_visibility=function(u,v)u.visible=v end}
        World={LINK_MODE_NODE_NAME=1,
          spawn_unit_ex=function(world,name) local u={alive=true,visible=true};units[#units+1]=u;return u end,
          destroy_unit=function(world,u)assert(u.alive);u.alive=false end,
          unlink_unit=function()end,link_unit=function()end}
        function require()return {}end
        local noop=function()end
        local registry={api={version=2,register=noop,changed=noop,owns=function()return active end}}
        local custom={is_api_compatible=function()return true end,
          acquire=function(owner,id,callback)
            requests[#requests+1]=id
            if not asset_exists(id)then return nil,'unknown custom asset '..id end
            callback();return {}
          end}
        owner={}
        function owner:get(k)
          if k:match('_outfit$')then return requested_outfit end
          if k=='jiggle'or k=='hide_body'then return false end
          if k=='model_variant'then return 'red'end
          if k=='jiggle_hang'then return .15 end
          if k:match('^jiggle_')then return 1 end
          if k=='jiggle_hair'or k=='jiggle_cloth'or k=='jiggle_stiffness'or k=='jiggle_damping'or k=='jiggle_limit'then return 1 end
          return true
        end
        function owner:is_enabled()return true end
        function owner:io_dofile(path)
          if path:match('/costume_catalog$')then return assert(loadstring(read_mod(path)))()end
          if path:match('/preview_lifecycle$')then return assert(loadstring(read_mod(path)))()end
          if path:match('/class_target$')then return {profile_matches=function()return active end,extension_matches=function()return active end}end
          if path:match('_jiggle$')then return {new=function()return {update=noop,clear=noop}end}end
          if path:match('/proportion_rig$')or path:match('/weapon_links$')then return {update=noop,clear=noop,release=noop}end
          return {body={},arms={},new=function()return {}end,update=noop,clear=noop}
        end
        function owner:hook_safe(cls,name,fn)
          if cls==CLASS.UIProfileSpawner then hooks[name]=fn end
        end
        function owner:hook(cls,name,fn)
          if cls==CLASS.UIProfileSpawner then hooks[name]=fn end
        end
        function owner:error(...)error(string.format(...))end
        owner.command=noop;owner.echo=noop;owner.set=noop
        shared={is_model_active=function()return active end,get_shared_option=function(k)return owner:get(k)end}
        function get_mod(id)
          if id=='AnimeModelReplacement'then return shared end
          if id=='ModelReplacementRegistry'then return registry end
          if id=='CustomAssets'then return custom end
          if id==provider_id then return owner end
        end
        function count_live()local n=0;for _,u in ipairs(units)do if u.alive then n=n+1 end end;return n end
        function new_spawner()
          local s={_world={},_visible=true,_character_spawn_data={unit_3p={alive=true},profile={archetype={breed='human'}},slots={},is_ready=true}}
          function s:_update_items_visibility()hooks._update_items_visibility(self)end
          return s
        end
        function dispose(s)
          return hooks._despawn_current_character_profile(function(self)
            -- Streaming/equipment refresh while original profile still exists.
            self:_update_items_visibility()
            self._character_spawn_data.unit_3p.alive=false
            self._character_spawn_data=nil
            return 'disposed',nil,17
          end,s)
        end
    ''')
    lua.execute((root / 'scripts/mods' / provider / (provider + '.lua')).read_text(encoding='utf-8-sig'))
    lua.globals().owner.on_all_mods_loaded()
    lua.execute('s=new_spawner();s:_update_items_visibility();assert(count_live()==1);a,b,c=dispose(s)')
    leaked = lua.globals().count_live()
    if leaked:
        return {'provider': provider, 'reentrant_teardown_orphans': leaked}
    lua.execute('''
        assert(a=='disposed'and b==nil and c==17,'Lost original returns')
        s=new_spawner();s:_update_items_visibility();s._character_spawn_data=nil
        s:_update_items_visibility();assert(count_live()==0,'Missing profile left visible mesh')
        s=new_spawner();s:_update_items_visibility()
        s._character_spawn_data.unit_3p.alive=false
        s:_update_items_visibility();assert(count_live()==0,'Deleted parent left visible mesh')
        -- Late update callbacks can arrive while the profile is being removed.
        s=new_spawner();s:_update_items_visibility()
        hooks._despawn_current_character_profile(function(self)
          hooks.update(self,.016)
          self:_update_items_visibility()
          self._character_spawn_data=nil
        end,s)
        assert(count_live()==0,'Update during teardown respawned a mesh')
        local slots={};for i=1,4 do slots[i]=new_spawner();slots[i]:_update_items_visibility()end
        assert(count_live()==4)
        for iteration=1,20 do
          local index=(iteration-1)%4+1
          dispose(slots[index]);slots[index]=new_spawner();slots[index]:_update_items_visibility()
          assert(count_live()==4,'Mission intro slot accumulated clones')
        end
        active=false;for _,slot in ipairs(slots)do slot:_update_items_visibility()end
        assert(count_live()==0,'Disabled provider left meshes')
        active=true;for _,slot in ipairs(slots)do slot:_update_items_visibility()end
        assert(count_live()==4)
        for _,slot in ipairs(slots)do dispose(slot)end
        assert(count_live()==0)
        s=new_spawner();s:_update_items_visibility()
        local ok=pcall(hooks._despawn_current_character_profile,function(self)
          self:_update_items_visibility();error('teardown failure sentinel')
        end,s)
        assert(not ok and count_live()==0)
        s:_update_items_visibility();assert(count_live()==1,'Guard remained stuck after error')
        dispose(s);assert(count_live()==0)
    ''')
    return {'provider': provider, 'reentrant_teardown_orphans': 0, 'four_slots_twenty_reassignments': True,
            'missing_parent_cleanup': True, 'deleted_parent_cleanup': True, 'update_during_teardown_safe': True,
            'original_return_values_preserved': True,
            'error_guard_restored': True, 'requested_assets': list(lua.globals().requests.values())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=pathlib.Path, default=ROOT)
    parser.add_argument('--expect-old-leak', action='store_true')
    parser.add_argument('--output', type=pathlib.Path)
    args = parser.parse_args()
    providers = sorted(p.name for p in (args.root / 'scripts/mods').iterdir() if p.name.endswith('Replacement') and p.name != 'AnimeModelReplacement')
    rows = [exercise(args.root, p) for p in providers]
    if args.expect_old_leak:
        assert all(row['reentrant_teardown_orphans'] == 1 for row in rows), rows
    else:
        assert all(row['reentrant_teardown_orphans'] == 0 for row in rows), rows
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PREVIEW_LIFECYCLE', len(rows), 'providers', 'old leak reproduced' if args.expect_old_leak else 'passed')
