import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scaffold_mod import scaffold
try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    LuaRuntime = None


@unittest.skipUnless(LuaRuntime, 'Install lupa==2.8 for Lua 5.1 syntax and lifecycle checks')
class LuaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lua = LuaRuntime(unpack_returned_tuples=True)

    def runtime(self, kind):
        candidate = self.root / ('candidate-' + kind); candidate.mkdir()
        profile = {'id': 'fixture_' + kind, 'kind': kind}
        if kind == 'weapon':
            profile.update(target_templates=['forcesword_p1_m1'], attachment_prefix='content/weapons/sword/attachments/')
        (candidate / 'build-report.json').write_text(json.dumps({'profile': profile}), encoding='utf-8')
        return scaffold(candidate, self.root / ('runtime-' + kind), 'Fixture' + kind.title())

    def test_all_archived_and_generated_lua_syntax(self):
        parse = self.lua.eval('function(s,n) local f,e=loadstring(s,n); assert(f,e); return true end')
        files = list((ROOT / 'toolbox').rglob('*.lua'))
        for kind in ('character', 'weapon'):
            runtime = self.runtime(kind)
            files += list(runtime.rglob('*.lua')) + list(runtime.glob('*.mod'))
        for file in files:
            with self.subTest(file=file.name):
                self.assertTrue(parse(file.read_text(encoding='utf-8'), str(file)))

    def load_character(self):
        runtime = self.runtime('character')
        self.lua.execute((ROOT / 'tests/fixtures/character_environment.lua').read_text(encoding='utf-8'))
        file = runtime / 'scripts/mods/FixtureCharacter/FixtureCharacter.lua'
        self.lua.execute(file.read_text(encoding='utf-8'))

    def test_character_native_ownership_and_deferred_release(self):
        self.load_character()
        self.lua.execute('''
            mod.on_all_mods_loaded(); resolve_requests()
            init_actor(); mod.update()
            assert(#spawned==2, 'body and arms expected')
            assert(native.alive and native_arms.alive, 'native units must survive')
            mod.enabled=false; mod.on_disabled(); mod.update()
            assert(#deletions==2, 'only custom units should retire')
            assert(#released==0, 'tickets must outlive deferred native deletion')
            for _,unit in ipairs(deletions) do unit.alive=false end
            mod.update(); assert(#released==2, 'unused body and arms tickets must release')
            assert(native.alive and native_arms.alive and actor.restored>0)
        ''')

    def test_character_stale_acquire_does_not_spawn(self):
        self.load_character()
        self.lua.execute('''
            mod.on_all_mods_loaded(); init_actor()
            mod.enabled=false; mod.on_disabled(); resolve_requests(); mod.update()
            assert(#spawned==0 and #released==2)
        ''')

    def test_character_world_teardown_prevents_native_calls(self):
        self.load_character()
        self.lua.execute('''
            mod.on_all_mods_loaded(); resolve_requests(); init_actor(); mod.update()
            local before=#spawned
            hooks['WorldManager:destroy_world'](function() world.destroyed=true end, {}, world)
            mod.update(); mod.enabled=false; mod.on_disabled(); mod.update()
            assert(#spawned==before and #deletions==0)
            assert(#released==2)
        ''')

    def load_weapon(self, ready=True):
        runtime = self.runtime('weapon')
        scripts = runtime / 'scripts/mods/FixtureWeapon'
        self.lua.globals().read_module = lambda name: (scripts / (name + '.lua')).read_text(encoding='utf-8')
        self.lua.execute((ROOT / 'tests/fixtures/weapon_environment.lua').read_text(encoding='utf-8'))
        self.lua.execute((scripts / 'FixtureWeapon.lua').read_text(encoding='utf-8'))
        self.lua.execute('mod.on_all_mods_loaded(); e.install(e.target)')
        if ready: self.lua.execute('e.load()')

    def test_weapon_native_ownership_return_tuple_and_deferred_release(self):
        self.load_weapon()
        self.lua.execute('''
            local f=e.fixture(true)
            local root,map,tail,gap,last=e.spawn(f)
            assert(root==f.root and map==f.map and tail=='tail' and gap==nil and last==17)
            local visual=e.visual(f); assert(visual and visual.parent==f.root and visual.fp)
            for _,unit in ipairs(f.original) do assert(unit.alive and not unit.visible) end
            e.enabled=false; mod.on_disabled(); mod.update(.01)
            assert(e.releases==0, 'ticket released before native deferred deletion')
            for _,unit in ipairs(f.original) do assert(unit.alive and unit.visible) end
            e.flush(); assert(e.releases==1)
        ''')

    def test_weapon_copies_shared_options_before_native_reentrant_callback(self):
        self.load_weapon()
        self.lua.execute('''
            local a=e.fixture(true); local b=e.fixture(false)
            e.hooks[e.target].spawn_item(function()
                e.options(b); b.world.dead=true; e.worlds[b.world]=nil
                return a.root,a.map
            end,a.item,e.options(a))
            assert(e.visual(a) and e.visual(a).fp and e.spawns==1)
        ''')

    def test_weapon_pending_cancelled_before_ui_spawner_teardown(self):
        self.load_weapon(False)
        self.lua.execute('''
            local f=e.fixture(false); e.spawn(f)
            e.hooks.UIUnitSpawner.destroy(function(owner) owner.destroyed=true end,f.spawner)
            e.load(); assert(e.spawns==0)
        ''')

    def test_weapon_queued_root_deletion_and_world_teardown_do_not_respawn(self):
        self.load_weapon()
        self.lua.execute('''
            local f=e.fixture(false); e.spawn(f); local before=e.spawns
            f.spawner:mark_for_deletion(f.root)
            mod.on_setting_changed('skin_model'); mod.update(.01)
            assert(e.spawns==before and not e.visual(f))
            local g=e.fixture(false); e.spawn(g); before=e.spawns
            e.hooks.WorldManager.destroy_world(function()
                e.spawn(g); g.world.dead=true; e.worlds[g.world]=nil
            end,{},g.world)
            mod.update(.01); assert(e.spawns==before)
        ''')


if __name__ == '__main__':
    unittest.main()
