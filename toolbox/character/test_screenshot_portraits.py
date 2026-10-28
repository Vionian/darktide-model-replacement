"""Exercise production HUD hooks with async resources and real native callbacks."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/model-work/python-deps'))
from lupa.luajit21 import LuaRuntime

lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute('''
CLASS={HudElementPlayerPanelBase={}}
hooks={}; requests={}; released=0; errors=0
local custom={}
function custom.acquire(owner,name,cb,options)
 assert(string.find(name,'AnimeModelReplacement:',1,true)==1 and options.resident and cb==nil)
 local ticket={status='pending',name=name};requests[#requests+1]=ticket;return ticket
end
function custom.release_owner(owner)released=released+1 end
local registry={api={version=2,winner=function()return winner end}}
function get_mod(id)if id=='CustomAssets'then return custom elseif id=='ModelReplacementRegistry'then return registry end end
mod={enabled=true,values={model_enabled=true},selection='RoshiaReplacement'}
function mod:is_enabled()return self.enabled end
function mod:get(k)return self.values[k]end
function mod.model_for_class(c)return mod.selection end
function mod.should_replace(...)return mod.enabled and mod.values.model_enabled end
function mod:hook(c,n,f)assert(c=='HudElementPlayerPanelBase');hooks[n]=f end
function mod:error(...)errors=errors+1 end
function fresh(class,breed)
 local p={style={texture={material_values={rows=4,columns=5,grid_index=7,texture_icon='atlas_A',use_placeholder_texture=0,desaturation=0,intensity=1}}},content={texture='custom_frame'},dirty=false}
 local s={_widgets_by_name={player_icon=p},_player={data={archetype={name=class or 'psyker',breed=breed or 'human'}}}}
 function s._player:profile()return self.data end
 function s:_get_player_portrait_frame_material(profile)return 'custom_frame'end
 return s,p.style.texture.material_values
end
function native_set(s,profile,grid,rows,cols,rt)
 local p=s._widgets_by_name.player_icon;local v=p.style.texture.material_values
 v.use_placeholder_texture=0;v.grid_index=grid-1;v.rows=rows;v.columns=cols;v.texture_icon=rt;p.content.texture='custom_frame'
end
function native_unset(s)
 local p=s._widgets_by_name.player_icon;local v=p.style.texture.material_values
 v.use_placeholder_texture=nil;v.grid_index=nil;v.rows=nil;v.columns=nil;v.texture_icon=nil;p.content.texture='no_render'
end
function update(s,f)hooks._update_player_features(f or function()end,s)end
winner='RoshiaReplacement'
''')
control = lua.execute((ROOT / 'scripts/mods/AnimeModelReplacement/screenshot_portraits.lua').read_text()).install(lua.globals().mod)
lua.globals().control = control
lua.execute('''
s,v=fresh();update(s)
assert(v.texture_icon=='atlas_A' and #requests==1,'pending resource must keep original')
requests[1].status='loaded';update(s)
assert(v.texture_icon=='content/mods/roshia/roshia_portrait' and v.grid_index==0 and v.rows==1 and v.columns==1)
assert(v.intensity==1 and v.desaturation==0,'status shading preserved')
for i=1,60 do update(s)end
assert(#requests==1,'ticket duplicated per frame')
-- An asynchronous atlas refresh must not overwrite the screenshot.
hooks._cb_set_player_icon(native_set,s,s._player:profile(),14,8,9,'atlas_B')
assert(v.texture_icon=='content/mods/roshia/roshia_portrait')
mod.selection='none';winner=nil;update(s)
assert(v.texture_icon=='atlas_B' and v.grid_index==13 and v.rows==8 and v.columns==9,'native baseline not restored')
mod.selection='RoshiaReplacement';winner=mod.selection
-- Cached captures can complete synchronously inside native update.
update(s,function(self)hooks._cb_set_player_icon(native_set,self,self._player:profile(),3,6,7,'atlas_C')end)
mod.selection='none';winner=nil;update(s)
assert(v.texture_icon=='atlas_C' and v.grid_index==2,'nested callback corrupted original baseline')
-- All twelve screenshot entries, six supported classes, same native frame.
local providers={'RoshiaReplacement','ChenqianyuReplacement','GilbertaReplacement','LiinoReplacement','MifuReplacement','PerlicaReplacement','TangtangReplacement','YvonneReplacement','ZhuangfangyiReplacement','AitelaReplacement','LaiwantingReplacement','SaixiReplacement'}
for _,provider in ipairs(providers)do
 mod.selection=provider;winner=provider
 for _,class in ipairs({'veteran','zealot','psyker','adamant','broker','cryptic'})do
  local p,values=fresh(class);update(p)
  for _,ticket in ipairs(requests)do ticket.status='loaded'end
  update(p);assert(string.find(values.texture_icon,'content/mods/',1,true)==1,provider)
  values.desaturation=1;values.intensity=.25;update(p)
  assert(values.desaturation==1 and values.intensity==.25)
  hooks.destroy(function(self)self.deleted=true end,p);assert(p.deleted and values.texture_icon=='atlas_A')
 end
end
assert(#requests==12,'one ticket per source texture')
local p,values=fresh('ogryn','ogryn');update(p);assert(values.texture_icon=='atlas_A','ogryn excluded')
mod.selection='UnpicturedModel';winner=mod.selection;p,values=fresh();update(p);assert(values.texture_icon=='atlas_A')
mod.selection='RoshiaReplacement';winner='DifferentProvider';update(p);assert(values.texture_icon=='atlas_A','must respect registry owner')
winner=mod.selection;update(p);hooks._cb_unset_player_icon(native_unset,p);assert(values.texture_icon==nil)
update(p);assert(values.texture_icon=='content/mods/roshia/roshia_portrait')
mod.enabled=false;control.suspend();assert(values.texture_icon==nil and p._widgets_by_name.player_icon.content.texture=='no_render')
mod.enabled=true;update(p);assert(values.texture_icon=='content/mods/roshia/roshia_portrait')
control.shutdown();assert(values.texture_icon==nil and released==1);update(p);assert(values.texture_icon==nil)
assert(errors==0)
''')
report = {'screenshots': 12, 'class_routes': 72, 'native_frame_and_status_preserved': True,
          'async_and_nested_callbacks': True, 'switch_disable_unload_restore': True,
          'ogryn_and_other_models_untouched': True, 'ticket_deduplication_and_release': True,
          'game_launched': False}
(ROOT / 'tools/model-work/distribution_fix/screenshot_portrait_checks.json').write_text(json.dumps(report, indent=2) + '\n')
print('SCREENSHOT_PORTRAITS_OK', report)
