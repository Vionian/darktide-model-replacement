"""Run all provider hooks together, with the game's MissionIntroView slot code.

Native rendering is mocked. This verifies ownership and visibility transitions,
not an in-game screenshot, bone animation, or material appearance.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/model-work/python-deps'))
from lupa.luajit21 import LuaRuntime


def exercise(root, expect_old=False):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().read_mod = lambda path: (root / (path.removeprefix('AnimeModelReplacement/') + '.lua')).read_text(encoding='utf-8-sig')
    lua.globals().asset_exists = lambda name: (root / 'Custom' / name.split(':')[-1] / 'build.json').is_file()
    lua.execute(r'''
      local noop=function()end
      owners={};units={};active_provider='ZhuangfangyiReplacement';intro_open=false
      CLASS={UIProfileSpawner={},PlayerUnitVisualLoadoutExtension={},PlayerHuskVisualLoadoutExtension={},PlayerVisibilityExtension={}}
      local records={}
      local function pack(...)return {n=select('#',...),...}end
      local function hook(cls,name,fn,safe)
        records[cls]=records[cls]or{}
        local r=records[cls][name]
        if not r then
          r={chain=cls[name]or noop,safe={}};records[cls][name]=r
          cls[name]=function(...)
            local out=pack(r.chain(...))
            for _,f in ipairs(r.safe)do f(...)end
            return unpack(out,1,out.n)
          end
        end
        if safe then r.safe[#r.safe+1]=fn else
          local previous=r.chain;r.chain=function(...)return fn(previous,...)end
        end
      end
      function new_owner(id)
        local o={id=id}
        function o:get(k)
          if k=='jiggle'or k=='hide_body'then return false end
          if k=='model_variant'then return 'red'end
          if k=='jiggle_hang'then return .15 end
          if k:match('^jiggle_')then return 1 end
          return true
        end
        function o:is_enabled()return true end
        function o:hook(cls,name,fn)hook(cls,name,fn,false)end
        function o:hook_safe(cls,name,fn)hook(cls,name,fn,true)end
        function o:io_dofile(path)
          if path:match('/preview_lifecycle$')then return assert(loadstring(read_mod(path)))()end
          if path:match('/class_target$')then return {
            profile_matches=function()return active_provider==id end,
            extension_matches=function()return active_provider==id end}end
          if path:match('_jiggle$')then return {new=function()return {update=noop,clear=noop}end}end
          if path:match('/auto_form$')then return {update=function(_,_,current)return current end}end
          if path:match('/proportion_rig$')or path:match('/weapon_links$')then return {update=noop,clear=noop,release=noop}end
          return {body={},arms={},new=function()return {}end,update=noop,clear=noop}
        end
        o.set=noop;o.command=noop;o.echo=noop;o.info=noop
        function o:error(...)error(string.format(...))end
        owners[id]=o;return o
      end
      shared=new_owner('AnimeModelReplacement')
      shared.is_model_active=function(id)return id==active_provider end
      shared.get_shared_option=function(k)return shared:get(k)end
      local registry={api={version=2,register=noop,changed=noop}}
      local custom={is_api_compatible=function()return true end,
        acquire=function(owner,id,callback)
          assert(asset_exists(id),'Missing asset '..id);callback();return {}
        end}
      function get_mod(id)
        if id=='CustomAssets'then return custom end
        if id=='ModelReplacementRegistry'then return registry end
        return owners[id]
      end
      Unit={alive=function(u)return u and u.alive end,has_node=function()return false end,world_pose=function()return {}end,
        world_position=function()return {}end,world_rotation=function()return {}end,
        set_unit_culling=noop,set_shader_pass_flag_for_meshes_in_unit_and_childs=noop,
        set_unit_visibility=function(u,v)assert(u.alive);u.visible=v and true or false end}
      World={LINK_MODE_NODE_NAME=1,
        spawn_unit_ex=function(world,name)
          local u={alive=true,visible=true,world=world,name=name};units[#units+1]=u;return u
        end,
        destroy_unit=function(world,u)assert(u.alive and u.world==world);u.alive=false end,
        link_unit=noop,unlink_unit=noop}
      ScriptUnit={has_extension=function(u,key)
        if key=='player_visibility_system'then return u.visibility end
      end}
      local player_manager={}
      function player_manager:players()return {}end
      function player_manager:human_players()return players end
      function player_manager:bot_players()return {}end
      function player_manager:local_player_safe()return players[1]end
      function player_manager:local_player()return players[1]end
      Managers={player=player_manager,ui={view_active=function(_,name)return intro_open and name=='mission_intro_view'end},
        event={trigger=noop},time={time=function()return 0 end}}
      settings={ignored_slots={},animations_per_archetype={veteran={'idle'}},prioritized_ogryn_sized_slots={3,5,4,6}}
      Vector3={to_array=function()return {}end,from_array=function()return {}end}
      QuaternionBox=setmetatable({unbox=function()return {}end},{__call=function()return {}end})
      math.next_random=function(seed,n)return seed+1,1 end
      function table.clear(t)for k in pairs(t)do t[k]=nil end end
      function class(name)
        CLASS[name]=CLASS[name]or{super={on_exit=noop}};return CLASS[name]
      end
      function require(path)
        if path:match('/ui_profile_spawner$')then return CLASS.UIProfileSpawner end
        if path:match('/mission_intro_view_settings$')then return settings end
        if path:match('/breeds$')then return {human={body_size='human'}}end
        return {}
      end
      local spawner=CLASS.UIProfileSpawner
      for _,vl in ipairs({CLASS.PlayerUnitVisualLoadoutExtension,CLASS.PlayerHuskVisualLoadoutExtension})do
        vl.destroy=function(self)
          self:force_update_item_visibility() -- Native gear callbacks during destruction.
          return 'disposed',nil,17
        end
      end
      function spawner:new(reference,world)
        return setmetatable({_reference_name=reference,_world=world,_visible=true,_character_toggle_state=true},{__index=self})
      end
      function spawner:ignore_slot()end
      function spawner:spawn_profile(profile)
        self._character_spawn_data={unit_3p={alive=true},profile=profile,slots={},is_ready=true}
        self:_update_items_visibility()
      end
      function spawner:_update_items_visibility()end
      function spawner:update()end
      function spawner:_despawn_current_character_profile()
        if self._character_spawn_data then
          self:_update_items_visibility()
          self._character_spawn_data.unit_3p.alive=false;self._character_spawn_data=nil
        end
      end
      function spawner:destroy()self:_despawn_current_character_profile()end
      function spawner:assign_animation_event()end
      players={}
      for i=1,4 do
        local profile={archetype={breed='human',name='veteran'}}
        players[i]={profile=function()return profile end,unique_id=function()return i end,
          is_human_controlled=function()return true end,slot=function()return i end,breed_name=function()return 'human'end}
      end
      function count_live(world,visible_only)
        local n=0
        for _,u in ipairs(units)do
          if u.alive and (not world or u.world==world)and(not visible_only or u.visible)then n=n+1 end
        end
        return n
      end
    ''')
    game_source = ROOT / 'tools/darktide-lua-source/scripts/ui/views/mission_intro_view/mission_intro_view.lua'
    lua.execute(game_source.read_text(encoding='utf-8-sig'))
    # Execute native hide/show API against the same replacement units.
    source_repo = ROOT / 'tools/darktide-lua-source'
    visibility_source = subprocess.check_output(['git', 'show', 'HEAD:scripts/extension_systems/player_visibility/player_visibility_extension.lua'], cwd=source_repo).decode('utf-8-sig')
    lua.execute(visibility_source)
    lua.execute('lifecycle=shared:io_dofile("AnimeModelReplacement/scripts/mods/AnimeModelReplacement/preview_lifecycle");if lifecycle.install then lifecycle.install(shared)end')
    providers = sorted(p.name for p in (root / 'scripts/mods').iterdir() if p.name.endswith('Replacement') and p.name != 'AnimeModelReplacement')
    for provider in providers:
        lua.eval('new_owner')(provider)
        lua.execute((root / 'scripts/mods' / provider / (provider + '.lua')).read_text(encoding='utf-8-sig'))
        lua.globals().owners[provider].on_all_mods_loaded()
    # Four occupied squad slots PLUS two independent cinematic spawners in
    # the same world. Previous teardown-only tests never exercised this path.
    lua.execute('''
      preview_world={};portrait_world={}
      view=setmetatable({_spawn_point_units={{},{},{},{},{},{}},_seed=0,
        _animation_events_used={},_num_animation_events_used=0,_prioritized_ogryn_sized_slots={3,5,4,6},
        _world_spawner={world=function()return preview_world end,camera=function()return {}end,
          unit_spawner=function()return {}end}}, {__index=CLASS.MissionIntroView})
      view:_setup_spawn_slots();view:_assign_player_slots()
      for _,slot in pairs(view._spawn_slots)do if slot.occupied then slot.profile_spawner:update(.016)end end
      assert(#view._spawn_slots==6);assert(count_live(preview_world,true)==4)
      extra={}
      for i=1,2 do
        extra[i]=CLASS.UIProfileSpawner:new('CutsceneCharacterExtension_'..i,preview_world)
        extra[i]:spawn_profile(players[1]:profile());extra[i]:update(.016)
      end
      extra_count=count_live(preview_world,true)-4
    ''')
    old_extra = lua.globals().extra_count
    if expect_old:
        assert old_extra == 2, old_extra
        return {'old_same_world_extras_reproduced': old_extra}
    assert old_extra == 0, f'Squad was joined by {old_extra} unauthorized models'
    lua.execute('''
      -- Model selection: full 16-provider hook chain, not isolated callbacks.
      for id in pairs(owners)do
        if id~='AnimeModelReplacement'then
          active_provider=id
          for _,slot in pairs(view._spawn_slots)do if slot.occupied then slot.profile_spawner:_update_items_visibility();slot.profile_spawner:update(.016)end end
          for _,s in ipairs(extra)do s:_update_items_visibility();s:update(.016)end
          assert(count_live(preview_world,true)==4,'Provider switch accumulated duplicates: '..id)
        end
      end
      active_provider='ZhuangfangyiReplacement'
      for _,slot in pairs(view._spawn_slots)do if slot.occupied then slot.profile_spawner:_update_items_visibility()end end
      -- A companion-only preview must not render the human container.
      portrait=CLASS.UIProfileSpawner:new('PortraitUI',portrait_world)
      portrait:spawn_profile(players[1]:profile());assert(count_live(portrait_world,true)==1)
      portrait._character_toggle_state=false;portrait:_update_items_visibility()
      assert(count_live(portrait_world)==0)
      portrait._character_toggle_state=true;portrait:_update_items_visibility()
      assert(count_live(portrait_world,true)==1,'Other UI worlds were incorrectly capped')
      -- Reclaim a preexisting auxiliary model when the view adopts a world.
      spare_world={};stale=CLASS.UIProfileSpawner:new('CutsceneCharacterExtension_old',spare_world)
      stale:spawn_profile(players[1]:profile());assert(count_live(spare_world)==1)
      spare_view=setmetatable({_spawn_point_units={{},{},{},{},{},{}},
        _world_spawner={world=function()return spare_world end,camera=function()return {}end,
          unit_spawner=function()return {}end,destroy=function()end}}, {__index=CLASS.MissionIntroView})
      spare_view:_setup_spawn_slots();assert(count_live(spare_world)==0,'Existing auxiliary model survived scene adoption')
      spare_view:on_exit()
    ''')
    # Exercise player visibility on a manually driven (unlinked) body. Snapshot
    # APIs intentionally operate only on the original actor, as in the engine.
    lua.execute('''
      intro_open=true
      gameplay_world={}
      driver={alive=true,visible=true}
      body=World.spawn_unit_ex(gameplay_world,'body')
      arms=World.spawn_unit_ex(gameplay_world,'arms')
      lifecycle.actor_subject(body,driver,true);lifecycle.actor_subject(arms,driver,false)
      assert(not body.visible and not arms.visible,'Gameplay actors leaked behind the squad')
      -- Close the authoritative view through the original on_exit path.
      view._world_spawner.destroy=function()end
      intro_open=false;view:on_exit()
      assert(count_live(preview_world)==0,'View exit leaked models')
      assert(body.visible and not arms.visible,'Gameplay visibility failed to restore')
      local snapshots={}
      Unit.take_visibility_snapshot=function(us)for _,u in ipairs(us)do snapshots[u]=u.visible end end
      Unit.restore_visibility_snapshot=function(us)for _,u in ipairs(us)do u.visible=snapshots[u]end end
      local visibility=setmetatable({_unit=driver,_unit_tbl={driver},_is_visible=true},{__index=CLASS.PlayerVisibilityExtension})
      driver.visibility=visibility
      visibility:hide();assert(not body.visible)
      lifecycle.actor_subject(body,driver,true);assert(not body.visible,'A refresh resurrected a hidden player')
      visibility:show();assert(body.visible)
      -- First-person arms retain their desired visibility across native snapshots.
      lifecycle.actor_subject(body,driver,false);lifecycle.actor_subject(arms,driver,true)
      visibility:hide();assert(not arms.visible)
      visibility:show();assert(arms.visible and not body.visible)
      lifecycle.release_actor(arms);lifecycle.release_actor(body)
      assert(not arms.visible and not body.visible,'Queued deletion left visible geometry')
      portrait:destroy();stale:destroy()
      -- Production gameplay providers, with deferred engine deletion. Switching
      -- models must not leave one-frame visible ghosts, including husks.
      actual_world={}
      Managers.state={unit_spawner={
        spawn_unit=function(_,name)return World.spawn_unit_ex(actual_world,name)end,
        mark_for_deletion=function(_,u)u.pending_delete=true end}}
      for _,vl in ipairs({CLASS.PlayerUnitVisualLoadoutExtension,CLASS.PlayerHuskVisualLoadoutExtension})do
      native={alive=true,visible=true};native_fp={alive=true,visible=true}
      ext={_unit=native,_first_person_unit=native_fp,_player=players[1],_equipment={},_is_in_first_person_mode=false}
      function ext:force_update_item_visibility()
        vl._update_item_visibility(self,self._is_in_first_person_mode)
      end
      vl.init(ext,{world=actual_world},native,{archetype={name='veteran',breed='human'}})
      for id in pairs(owners)do
        if id~='AnimeModelReplacement'then
          active_provider=id;ext:force_update_item_visibility()
          assert(count_live(actual_world,true)==1,'Gameplay switch left visible duplicates: '..id)
          ext._is_in_first_person_mode=true;ext:force_update_item_visibility()
          assert(count_live(actual_world,true)==1,'First-person switch left visible body: '..id)
          intro_open=true;vl.update(ext,native,.016,1)
          assert(count_live(actual_world,true)==0,'Provider leaked gameplay actor in intro: '..id)
          intro_open=false;vl.update(ext,native,.016,1)
          assert(count_live(actual_world,true)==1,'Provider failed to restore arms: '..id)
          ext._is_in_first_person_mode=false
        end
      end
      local a,b,c=vl.destroy(ext)
      assert(a=='disposed'and b==nil and c==17,'Gameplay teardown changed original returns')
      assert(count_live(actual_world,true)==0,'Extension destroy left visible queued units')
      end
      lifecycle.reset()
    ''')
    return {'combined_providers': len(providers), 'real_mission_intro_slot_code': str(game_source),
            'six_candidate_slots_four_occupied': True, 'same_world_auxiliary_spawners_blocked': True,
            'all_provider_switches_keep_four': True, 'other_world_portrait_unaffected': True,
            'companion_only_human_container_hidden': True, 'gameplay_actor_hidden_during_intro': True,
            'native_visibility_snapshot_hide_show': True, 'first_person_visibility_restored': True,
            'production_gameplay_provider_switches': len(providers),
            'player_and_husk_reentrant_teardown': True,
            'exit_cleans_models': True, 'queued_deletion_hidden_immediately': True,
            'in_game_validation': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--expect-old', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = exercise(args.root, args.expect_old)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
