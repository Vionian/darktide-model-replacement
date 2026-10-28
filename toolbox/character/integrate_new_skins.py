"""Extend the tested Si costume lifecycle with character-specific resources."""
from pathlib import Path
import json,shutil
from skins_sources import SOURCES,OUT
from adapt_skins import VARIANTS
ROOT=Path(__file__).resolve().parents[2];MODS=ROOT/'scripts/mods'
PROVIDERS={'roshia':'RoshiaReplacement','endministrator_f':'EndministratorReplacement',
 'si':'SiReplacement','perlica':'PerlicaReplacement','mifu':'MifuReplacement',
 'gilberta':'GilbertaReplacement','saixi':'SaixiReplacement','aitela':'AitelaReplacement',
 'laiwanting':'LaiwantingReplacement','chenqianyu':'ChenqianyuReplacement'}
def lua(v):
    if isinstance(v,str):return json.dumps(v,ensure_ascii=False)
    if isinstance(v,int):return str(v)
    if isinstance(v,list):return '{'+','.join(lua(x)for x in v)+'}'
    return '{'+','.join('['+lua(k)+']='+lua(x)for k,x in v.items())+'}'
def main():
    backup=OUT/'runtime_before';backup.mkdir(exist_ok=True)
    for provider in [*PROVIDERS.values(),'AnimeModelReplacement']:
        dst=backup/provider;dst.mkdir(exist_ok=True)
        for f in (MODS/provider).glob('*.lua'):
            if not (dst/f.name).exists():shutil.copy2(f,dst/f.name)
    ui=MODS/'AnimeModelReplacement';catalog={}
    for base,provider in PROVIDERS.items():
        entries=[dict(id='original',title='skin_original',asset=base,variants=1)]
        if base=='si':
            for name in ('ink_mist','short_skirt','lolita'):
                entries.append(dict(id=name,title='skin_si_'+name,asset='si_'+name,variants=1))
        for key,(folder,parent,ini)in SOURCES.items():
            if parent==base:entries.append(dict(id=key[len(base)+1:]if key.startswith(base+'_')else key,
                title='skin_'+key,asset=key,variants=VARIANTS[key]))
        catalog[provider]=dict(setting=base+'_outfit',base=base,outfits=entries)
    (ui/'costume_catalog.lua').write_text('-- Each outfit owns its body, arms and skeleton configuration.\nreturn '+lua(catalog)+'\n',encoding='utf8')
    (OUT/'costume_catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf8')
    template=(backup/'SiReplacement/SiReplacement.lua').read_text(encoding='utf8')
    for base,provider in PROVIDERS.items():
        s=template.replace('SiReplacement',provider).replace('__si','__'+base).replace('/si_','/'+base+'_')
        start=s.index('local ink_jiggle_config =');end=s.index('local weapon_links =',start)
        s=s[:start]+s[end:]
        start=s.index('local OUTFITS =');end=s.index('-- All material/shader streams',start)
        block=(Path(__file__).parent/'new_skin_runtime_block.lua').read_text(encoding='utf8')
        s=s[:start]+block+'\n'+s[end:]
        s=s.replace('setting_id == "si_outfit"','costume_setting_changed(setting_id)')
        s=s.replace('local outfit = OUTFITS[opt("si_outfit")] and opt("si_outfit") or "original"','local outfit = resolve_outfit()')
        s=s.replace('-- 祀 Class Replacement 1.0.0','-- '+provider+' with source-specific costumes')
        # Every provider owns one short, stable command. Keeping /si only on
        # SiReplacement prevents DMF's global command registry collisions.
        command={'roshia':'roshia','endministrator_f':'endministrator','si':'si',
                 'perlica':'perlica','mifu':'mifu','gilberta':'gilberta','saixi':'saixi',
                 'aitela':'aitela','laiwanting':'laiwanting','chenqianyu':'chenqianyu'}[base]
        s=s.replace('mod:command("si",','mod:command("'+command+'",')
        (MODS/provider/(provider+'.lua')).write_text(s,encoding='utf8')
    (ui/'AnimeModelReplacement_data.lua').write_text((Path(__file__).parent/'new_skin_settings.lua').read_text(encoding='utf8'),encoding='utf8')
    p=ui/'AnimeModelReplacement_localization.lua';s=p.read_text(encoding='utf8')
    text={'skin_original':'原版','skin_outfit':'服装','skin_variation':'服装配色／款式',
          'skin_si_ink_mist':'墨雾','skin_si_short_skirt':'短裙','skin_si_lolita':'洛丽塔'}
    text.update({'skin_'+k:v[0].split('-')[0]for k,v in SOURCES.items()})
    text.update({'skin_variant_'+str(i):'服装 '+str(i)for i in range(1,5)})
    if 'skin_original ='not in s:
        s=s[:s.rfind('}')]+''.join('\t'+k+' = {["zh-cn"]='+lua(v)+', en='+lua(v)+'},\n'for k,v in text.items())+'}\n'
        p.write_text(s,encoding='utf8')
    p=ui/'AnimeModelReplacement.lua';s=p.read_text(encoding='utf8')
    needle='function mod.get_shared_option(key)\n'
    extra='\t-- Removed controls always use authored defaults, including old saved settings.\n\tif key == "hide_body" or key == "jiggle" then return true end\n\tif string.sub(key, 1, 7) == "jiggle_" then return nil end\n'
    if 'Removed controls always use authored defaults'not in s:s=s.replace(needle,needle+extra)
    p.write_text(s,encoding='utf8')
    print('COSTUME_RUNTIME_INTEGRATED',len(catalog),'providers')
if __name__=='__main__':main()
