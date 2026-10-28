"""Production Lua variant lifecycle, not a string-only settings check."""
import inspect,json,pathlib,sys
HERE=pathlib.Path(__file__).parent
sys.path.insert(0,str(HERE))
from test_preview_lifecycle import exercise,ROOT
TARGET=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else ROOT

code=inspect.getsource(exercise)
code=code.replace("if k=='model_variant'then return 'red'end", "if k=='model_variant'then return 'red'end; if k=='si_outfit'then return outfit or 'original'end")
code=code.replace('local u={alive=true,visible=true}', 'local u={alive=true,visible=true,name=name}')
needle="    return {'provider': provider, 'reentrant_teardown_orphans': 0"
probe='''    lua.execute("""
        active=true
        local slots={};for i=1,4 do slots[i]=new_spawner();slots[i]:_update_items_visibility()end
        assert(count_live()==4)
        local outfits={'original','ink_mist','short_skirt','lolita'}
        for iteration=1,40 do
            outfit=outfits[(iteration-1)%4+1]
            owner.on_setting_changed('si_outfit')
            assert(count_live()==4,'Outfit switch duplicated/dropped preview actors')
            for _,s in ipairs(slots)do
                local asset=outfit=='original' and 'si' or 'si_'..outfit
                assert(s.__si_unit.name=='content/mods/'..asset..'/'..asset)
            end
        end
        for _,s in ipairs(slots)do dispose(s)end
        assert(count_live()==0)
        assert(#requests==8,'Each body/arms variant must be acquired once')
        local seen={};for _,id in ipairs(requests)do assert(not seen[id]);seen[id]=true end
        assert(seen['AnimeModelReplacement:si'] and seen['AnimeModelReplacement:si_arms'])
        assert(seen['AnimeModelReplacement:si_ink_mist'] and seen['AnimeModelReplacement:si_ink_mist_arms'])
        assert(seen['AnimeModelReplacement:si_short_skirt'] and seen['AnimeModelReplacement:si_short_skirt_arms'])
        assert(seen['AnimeModelReplacement:si_lolita'] and seen['AnimeModelReplacement:si_lolita_arms'])
    """)
'''
code=code.replace(needle,probe+needle)
namespace=dict(exercise.__globals__)
exec(compile(code,__file__,'exec'),namespace)
result=namespace['exercise'](TARGET,'SiReplacement')

from lupa.luajit21 import LuaRuntime
lua=LuaRuntime(unpack_returned_tuples=True)
lua.globals().read_ui_module=lambda p:(TARGET/(p.removeprefix('AnimeModelReplacement/')+'.lua')).read_text(encoding='utf8')
lua.execute("get_mod=function()return {localize=function(_,k)return k end,io_dofile=function(_,p)return assert(loadstring(read_ui_module(p)))()end}end")
data_code=(TARGET/'scripts/mods/AnimeModelReplacement/AnimeModelReplacement_data.lua').read_text(encoding='utf8')
data=lua.execute(data_code)
model=data.options.widgets[3]
assert model.sub_widgets[2].setting_id=='si_outfit'
assert model.sub_widgets[2].default_value=='original'
for _,option in model.options.items():
    if option.value=='SiReplacement':assert list(option.show_widgets.values())==[2]
    if option.value=='DaniyaReplacement':assert list(option.show_widgets.values())==[1]
result.update(outfit_switches_in_four_preview_slots=40,distinct_packages=8,independent_Daniya_and_Si_widgets=True)
from package_share_variants import asset_names,endfield_settings
assert asset_names('si')==('si','si_arms','si_ink_mist','si_ink_mist_arms',
                           'si_short_skirt','si_short_skirt_arms','si_lolita','si_lolita_arms')
lua.execute('''
    local definitions=get_mod():io_dofile('AnimeModelReplacement/scripts/mods/AnimeModelReplacement/model_definitions')
    for i=#definitions.models,1,-1 do
        local m=definitions.models[i]
        if m.id=='DaniyaReplacement' or m.id=='QianxiaReplacement' or m.id=='AimisiReplacement' then
            table.remove(definitions.models,i)
        elseif m.id=='SiReplacement' then m.option_widgets={1} end
    end
    get_mod=function()return {localize=function(_,k)return k end,io_dofile=function()return definitions end}end
''')
endfield=lua.execute(endfield_settings(data_code))
assert len(endfield.options.widgets[1].sub_widgets)==5
options=endfield.options.widgets[3]
assert options.default_value=='SiReplacement'
assert len(options.sub_widgets)==1 and options.sub_widgets[1].setting_id=='si_outfit'
for _,option in options.options.items():
    if option.value=='SiReplacement':assert list(option.show_widgets.values())==[1]
    assert option.value not in ('DaniyaReplacement','QianxiaReplacement','AimisiReplacement')
parse=lua.eval('function(s)local f,e=loadstring(s);assert(f,e)end')
parsed=0
for directory in ('AnimeModelReplacement','SiReplacement'):
    for f in (TARGET/'scripts/mods'/directory).glob('*.lua'):
        text=f.read_text(encoding='utf8');parse(text);parsed+=1
result.update(root=str(TARGET),endfield_share_outfit_preserved=True,share_asset_closure=True,lua_files_parsed=parsed)
name='variant_audit.json' if TARGET==ROOT else 'installed_variant_audit.json'
(HERE/'si_ink_mist'/name).write_text(json.dumps(result,indent=2),encoding='utf8')
print('SI_OUTFIT_LUA_OK',result)
