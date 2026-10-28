import pathlib,json,sys,re,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/model-work/python-deps'))
from lupa import LuaRuntime
from integrate_endfield_batch import PROFILES
lua=LuaRuntime(unpack_returned_tuples=True)
lua.execute('''mods={}; registered={}; settings={model_enabled=true,menu_previews=true}
CLASS={MissionIntroView={},PlayerVisibilityExtension={},PlayerUnitVisualLoadoutExtension={},
       PlayerHuskVisualLoadoutExtension={},PortraitUI={},HudElementPlayerPanelBase={}}
fassert=assert
new_mod=function(id,params) assert(not registered[id],id);registered[id]=params end
get_mod=function(id)
 if not mods[id] then mods[id]={localize=function(_,k)return k end,
 get=function(_,k)return settings[k] end,set=function(_,k,v)settings[k]=v end,
 command=function()end,hook=function()end,hook_safe=function()end,
 is_enabled=function()return true end} end
 return mods[id]
end''')
def read(p):return p.read_text(encoding='utf-8-sig')
def dofile(_,name):
    assert name.startswith('AnimeModelReplacement/')
    p=ROOT/(name.removeprefix('AnimeModelReplacement/')+'.lua')
    assert p.exists(),p
    return lua.execute(read(p))
for name in ('AnimeModelReplacement',):lua.globals().get_mod(name).io_dofile=dofile
desc=lua.execute(read(ROOT/'AnimeModelReplacement.mod'));desc.run()
defs=lua.execute(read(ROOT/'scripts/mods/AnimeModelReplacement/model_definitions.lua'))
loc=lua.execute(read(ROOT/'scripts/mods/AnimeModelReplacement/AnimeModelReplacement_localization.lua'))
data=lua.execute(read(ROOT/'scripts/mods/AnimeModelReplacement/AnimeModelReplacement_data.lua'))
lua.execute(read(ROOT/'scripts/mods/AnimeModelReplacement/AnimeModelReplacement.lua'))
mod=lua.globals().get_mod('AnimeModelReplacement');settings=lua.globals().settings
assert len(defs.models)==9
report={}
compile_=lua.eval('function(s)local f,e=load(s);return f~=nil,e end')
for key,(label,provider) in PROFILES.items():
    descriptor=lua.globals().registered[provider];assert descriptor
    for _,p in descriptor.items():assert (ROOT/(p.removeprefix('AnimeModelReplacement/')+'.lua')).exists(),p
    files=list((ROOT/'scripts/mods'/provider).glob('*.lua'))
    for f in files:
        text=read(f);ok,err=compile_(text);assert ok,(f,err)
        for dep in re.findall(r'io_dofile\("(AnimeModelReplacement/[^"\n]+)"\)',text):
            assert (ROOT/(dep.removeprefix('AnimeModelReplacement/')+'.lua')).exists(),dep
        assert 'RoshiaReplacement' not in text,(f,'provider collision')
    assert loc['model_'+key]['zh-cn']==label
    for _,cls in defs.classes.items():
        settings['model_'+cls.id]=provider
        for surface in ('body','preview','arms'):
            assert mod.should_replace(provider,cls.id,surface,'human')
            assert not mod.should_replace(provider,cls.id,surface,'ogryn')
    settings.menu_previews=False
    assert not mod.should_replace(provider,'veteran','preview','human')
    settings.menu_previews=True
    counts={}
    for asset in (key,key+'_arms'):
        folder=ROOT/'Custom'/asset
        build=json.loads((folder/'build.json').read_text(encoding='utf-8'))
        for a in build['artifacts']:
            target=folder/a['path'];assert target.is_file() and target.stat().st_size==a['size'],target
            candidate=ROOT/'tools/model-work/endfield_batch'/key/'Custom'/asset/a['path']
            assert hashlib.sha256(target.read_bytes()).digest()==hashlib.sha256(candidate.read_bytes()).digest(),target
            assert a['resource']['name'].startswith('content/mods/'+key+'/')
        assert all(a['key']['name']=='content/parent_materials/substance_basic' for a in build['external_resources'])
        counts[asset]=len(build['artifacts'])
    assert len(data.options.widgets[1].sub_widgets)==6
    assert all(len(v.options)==9 for _,v in data.options.widgets[1].sub_widgets.items())
    report[key]={'provider':provider,'lua_files':len(files),'artifacts':counts,'six_class_routes':True,'ogryn_excluded':True}
out=ROOT/'tools/model-work/endfield_batch/integration_audit.json'
out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ENDFIELD_INTEGRATION_AUDIT_OK',report)
