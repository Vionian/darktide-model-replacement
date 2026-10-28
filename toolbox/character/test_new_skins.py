"""Exercise production Lua and real settings; no live game claim."""
import inspect,json,sys,re
from pathlib import Path
HERE=Path(__file__).parent;sys.path.insert(0,str(HERE))
from test_preview_lifecycle import exercise,ROOT
from skins_sources import OUT
from lupa.luajit21 import LuaRuntime
catalog=json.loads((OUT/'costume_catalog.json').read_text(encoding='utf8'))
code=inspect.getsource(exercise)
code=code.replace("if path:match('/preview_lifecycle$')then", "if path:match('/preview_lifecycle$')or path:match('/costume_catalog$')then")
code=code.replace("function owner:get(k)","function owner:get(k)\n          if selected_settings and selected_settings[k]~=nil then return selected_settings[k] end")
code=code.replace('local u={alive=true,visible=true}', 'local u={alive=true,visible=true,name=name}')
probe='''    lua.execute("""
        active=true; selected_settings={}
        local catalog=owner:io_dofile('AnimeModelReplacement/scripts/mods/AnimeModelReplacement/costume_catalog')[provider_id]
        local slots={};for i=1,4 do slots[i]=new_spawner();slots[i]:_update_items_visibility()end
        assert(count_live()==4)
        for cycle=1,3 do
          for _,entry in ipairs(catalog.outfits)do
            for variant=1,entry.variants do
              selected_settings[catalog.setting]=entry.id
              selected_settings[entry.asset..'_variant']=variant
              owner.on_setting_changed(catalog.setting)
              owner.on_setting_changed(entry.asset..'_variant')
              assert(count_live()==4,'Outfit/color switch accumulated preview actors')
              local asset=entry.asset..(variant>1 and '_v'..variant or '')
              for _,s in ipairs(slots)do
                local found=false
                for k,v in pairs(s)do
                  if type(k)=='string'and k:match('_unit$')and type(v)=='table'and v.name then
                    assert(v.name=='content/mods/'..asset..'/'..asset);found=true
                  end
                end
                assert(found,'Missing selected preview outfit')
              end
            end
          end
        end
        for _,s in ipairs(slots)do dispose(s)end
        assert(count_live()==0)
        local seen={};for _,id in ipairs(requests)do assert(not seen[id],'Duplicate acquire');seen[id]=true end
    """)
'''
code=code.replace("    return {'provider': provider, 'reentrant_teardown_orphans': 0",probe+"    return {'provider': provider, 'reentrant_teardown_orphans': 0")
namespace=dict(exercise.__globals__);exec(compile(code,__file__,'exec'),namespace)
rows=[] if '--ui-only'in sys.argv else [namespace['exercise'](ROOT,p)for p in catalog]
assert all(r['reentrant_teardown_orphans']==0 for r in rows)
lua=LuaRuntime(unpack_returned_tuples=True)
lua.globals().read_module=lambda p:(ROOT/(p.removeprefix('AnimeModelReplacement/')+'.lua')).read_text(encoding='utf8')
lua.execute("get_mod=function()return {localize=function(_,k)return k end,io_dofile=function(_,p)return assert(loadstring(read_module(p)))()end}end")
ui=lua.execute((ROOT/'scripts/mods/AnimeModelReplacement/AnimeModelReplacement_data.lua').read_text(encoding='utf8'))
localization=lua.execute((ROOT/'scripts/mods/AnimeModelReplacement/AnimeModelReplacement_localization.lua').read_text(encoding='utf8'))
ids=[]
def check(widget):
    if widget.setting_id:ids.append(widget.setting_id)
    if widget.type=='dropdown':assert len(widget.options)>=2,('DMF dropdown needs at least two choices',widget.setting_id)
    if widget.type=='keybind':raise AssertionError('Shortcut remains visible')
    if widget.title:assert localization[widget.title],widget.title
    if widget.sub_widgets:
        for _,w in widget.sub_widgets.items():check(w)
    if widget.options:
        for _,option in widget.options.items():
            assert localization[option.text],option.text
            if option.show_widgets:
                for _,index in option.show_widgets.items():assert widget.sub_widgets[index],index
for _,w in ui.options.widgets.items():check(w)
assert len(ids)==len(set(ids))
assert not any(k.startswith('jiggle')or 'keybind'in k or k=='hide_body' for k in ids)
for c in catalog.values():
    if len(c['outfits'])>1:assert c['setting']in ids
    else:assert c['setting']not in ids,('Single-outfit selector must stay hidden',c['setting'])
assert 'endministrator_devil_variant'in ids
assert 'roshia_lolita_variant' not in ids
parse=lua.eval('function(s)local f,e=loadstring(s);assert(f,e)end')
parsed=0
for f in (ROOT/'scripts').rglob('*.lua'):parse(f.read_text(encoding='utf-8-sig'));parsed+=1
commands={}
for f in (ROOT/'scripts/mods').glob('*/*.lua'):
    for command in re.findall(r'mod:command\(\s*"([^"]+)"',f.read_text(encoding='utf-8-sig')):
        assert command not in commands, ('Duplicate chat command',command,commands.get(command),str(f))
        commands[command]=f.relative_to(ROOT).as_posix()
assert commands['si']=='scripts/mods/SiReplacement/SiReplacement.lua'
assert 'perlica_jk' not in json.dumps(catalog)
report=dict(lifecycle=rows,settings_ids=ids,lua_files_parsed=parsed,chat_commands=commands,real_game_verified=False)
(OUT/('ui_audit.json'if '--ui-only'in sys.argv else 'runtime_audit.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('NEW_SKINS_LUA_SETTINGS_OK',len(rows),'providers',parsed,'Lua files')
