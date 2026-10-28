"""Install audited batch candidates into the workspace unified mod, not the game."""
import pathlib,json,shutil,datetime,re,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).parent
PROFILES={'lizhiyan':('李织烟','LizhiyanReplacement'),
          'endministrator_f':('女管理员','EndministratorReplacement'),
          'si':('祀','SiReplacement'),'typhoea':('提弗洛斯','TyphoeaReplacement')}

def main():
    runtime_only='--runtime-only' in sys.argv
    assets_only='--assets-only' in sys.argv
    if runtime_only and assets_only:raise ValueError('Choose runtime-only or assets-only')
    backup=HERE/'endfield_batch'/('integration_backup_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    managed=['AnimeModelReplacement.mod','scripts/mods/AnimeModelReplacement/model_definitions.lua',
             'scripts/mods/AnimeModelReplacement/AnimeModelReplacement_localization.lua']
    if assets_only:managed=[]
    for path in managed:
        dest=backup/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/path,dest)
    for key,(label,provider) in PROFILES.items():
        candidate=HERE/'endfield_batch'/key
        for report in (() if runtime_only else ('asset_audit.json','contact_runtime_audit.json','source_hand_audit.json')):
            if not (candidate/report).exists():raise FileNotFoundError(candidate/report)
        for asset in (() if runtime_only else (key,key+'_arms')):
            src=candidate/'Custom'/asset;dest=ROOT/'Custom'/asset
            if dest.exists():shutil.copytree(dest,backup/'Custom'/asset)
            if assets_only:
                manifest=json.loads((src/'build.json').read_text(encoding='utf-8'))
                for relative in [a['path']for a in manifest['artifacts']]+['build.json','compile_manifest.json']:
                    source=(src/relative).resolve();target=(dest/relative).resolve()
                    if not source.is_relative_to(src.resolve())or not target.is_relative_to(dest.resolve()):
                        raise ValueError('Unsafe resource path: '+relative)
                    target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(source,target)
            else:shutil.copytree(src,dest,dirs_exist_ok=True)
        if assets_only:continue
        dest=ROOT/'scripts/mods'/provider;dest.mkdir(exist_ok=True)
        source=ROOT/'scripts/mods/RoshiaReplacement'
        for path in source.glob('*.lua'):
            if path.name in ('fp_hands.lua','roshia_jiggle_bones.lua','roshia_proportion_bones.lua'):continue
            filename=path.name.replace('RoshiaReplacement',provider).replace('roshia',key)
            text=path.read_text(encoding='utf-8').replace('RoshiaReplacement',provider).replace('roshia',key).replace('洛茜',label).replace('Roshia',label)
            if path.name=='RoshiaReplacement.lua':
                text=text.replace('local MATERIAL_TEMPLATE_ASSET = "AnimeModelReplacement:qianxia"','-- All material/shader streams are packaged with this model.')
                if 'local function acquire_material_template()'in text:
                    start=text.index('local function acquire_material_template()')
                    end=text.index('\nmod.on_all_mods_loaded',start)
                    text=text[:start]+'local function acquire_material_template()\n    acquire_model_assets()\nend\n'+text[end:]
            (dest/filename).write_text(text,encoding='utf-8')
        for suffix in ('jiggle_bones.lua','proportion_bones.lua'):
            shutil.copy2(candidate/'Custom'/(key+'_'+suffix),dest/(key+'_'+suffix))
    if assets_only:
        print('ENDFIELD_ASSETS_INTEGRATED',list(PROFILES),'backup',backup);return
    if runtime_only:
        print('ENDFIELD_RUNTIME_STAGED');return
    path=ROOT/'AnimeModelReplacement.mod';text=path.read_text(encoding='utf-8')
    anchor='\n\tend,\n\tpackages = {}'
    declarations=''
    for key,(label,provider) in PROFILES.items():
        if f'new_mod("{provider}"' in text:continue
        declarations+='\n\t\tnew_mod("'+provider+'", {\n'+''.join('\t\t\t'+field+' = "AnimeModelReplacement/scripts/mods/'+provider+'/'+provider+suffix+'",\n' for field,suffix in [('mod_script',''),('mod_data','_data'),('mod_localization','_localization')])+'\t\t})\n'
    text=text.replace(anchor,declarations+anchor);path.write_text(text,encoding='utf-8')
    path=ROOT/managed[1];text=path.read_text(encoding='utf-8')
    for key,(label,provider) in PROFILES.items():
        if f'id = "{provider}"' not in text:
            text=text.replace('\n\t},\n}',f'\n\t\t{{ id = "{provider}", title = "model_{key}", breeds = {{ human = true, cryptic = true }} }},\n\t}},\n}}')
    path.write_text(text,encoding='utf-8')
    path=ROOT/managed[2];text=path.read_text(encoding='utf-8')
    for key,(label,provider) in PROFILES.items():
        if 'model_'+key+' =' not in text:
            text=text.replace('\n\tclass_veteran =',f'\n\tmodel_{key} = {{ ["zh-cn"] = "{label}", en = "{provider.removesuffix("Replacement")}" }},\n\tclass_veteran =')
    text=text.replace('千咲和洛茜；','千咲、洛茜、李织烟、女管理员、祀和提弗洛斯；').replace('and Roshia are available',', Roshia, Lizhiyan, female Endministrator, Si and Typhoea are available')
    path.write_text(text,encoding='utf-8')
    print('ENDFIELD_WORKSPACE_INTEGRATED',list(PROFILES),'backup',backup)

if __name__=='__main__':main()
