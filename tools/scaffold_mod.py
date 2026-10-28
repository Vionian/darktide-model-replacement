"""Generate a baseline DMF runtime from a built character or weapon profile."""
import argparse
import json
from pathlib import Path
import re
import shutil

from darktide import ROOT, save_json


def lua(value):
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        raise ValueError('Lua profile strings must be text without control characters')
    return json.dumps(value, ensure_ascii=False)


def scaffold(candidate, output, mod_id):
    candidate, output = Path(candidate).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Choose a fresh runtime directory')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{1,63}', mod_id):
        raise ValueError('Mod ID must be 2-64 ASCII letters, digits or underscores, starting with a letter')
    profile = json.loads((candidate / 'build-report.json').read_text(encoding='utf-8'))['profile']
    if profile.get('kind') not in ('character', 'weapon') or not re.fullmatch(r'[a-z][a-z0-9_]{1,47}', profile.get('id', '')):
        raise ValueError('Invalid candidate profile identity')
    if profile['kind'] == 'weapon':
        if not profile.get('target_templates') or not all(re.fullmatch(r'[A-Za-z0-9_]+', x) for x in profile['target_templates']):
            raise ValueError('Weapon profile must contain valid template names')
        if not re.fullmatch(r'content/[A-Za-z0-9_/]+/', profile.get('attachment_prefix', '')):
            raise ValueError('Weapon attachment_prefix must be a content/ path ending in /')
    scripts = output / 'scripts/mods' / mod_id
    scripts.mkdir(parents=True)
    prefix = f'{mod_id}/scripts/mods/{mod_id}/{mod_id}'
    (output / (mod_id + '.mod')).write_text(
        'return {run=function() new_mod(' + lua(mod_id) + ', {mod_script=' + lua(prefix) +
        ', mod_data=' + lua(prefix + '_data') + ', mod_localization=' + lua(prefix + '_localization') +
        '}) end, packages={}}\n', encoding='utf-8')
    if profile['kind'] == 'character':
        content = (ROOT / 'templates/character.lua').read_text(encoding='utf-8')
        content = content.replace('__MOD_ID__', mod_id).replace('__ASSET_ID__', profile['id'])
        (scripts / (mod_id + '.lua')).write_text(content, encoding='utf-8')
        options = '{setting_id="first_person_arms",type="checkbox",default_value=true},'
    else:
        content = (ROOT / 'templates/weapon.lua').read_text(encoding='utf-8')
        content = content.replace('__MOD_ID__', mod_id).replace('__ASSET_ID__', profile['id'])
        (scripts / (mod_id + '.lua')).write_text(content, encoding='utf-8')
        for name in ('particle_controls.lua', 'viewmodel.lua'):
            text = (ROOT / 'toolbox/runtime/weapon/scripts/mods/WeaponModelReplacement' / name).read_text(encoding='utf-8')
            if name == 'viewmodel.lua':
                text = text.replace('or 3', 'or 0').replace('cm = 3', 'cm = 0')
            (scripts / name).write_text(text.replace('WeaponModelReplacement', mod_id), encoding='utf-8')
        templates = profile.get('target_templates', [])
        if not templates or not profile.get('attachment_prefix'):
            raise ValueError('Weapon profile must identify target_templates and attachment_prefix')
        template_map = ','.join('[' + lua(name) + ']=true' for name in templates)
        selection = (ROOT / 'templates/weapon_selection.lua').read_text(encoding='utf-8')
        for token, value in {
            '__MOD_ID__': mod_id, '__ASSET_ID__': profile['id'], '__TEMPLATE_MAP__': template_map,
            '__ATTACHMENT_PREFIX__': profile['attachment_prefix'],
        }.items():
            selection = selection.replace(token, value)
        (scripts / 'selection.lua').write_text(selection, encoding='utf-8')
        options = '{setting_id="skin_model",type="dropdown",default_value=' + lua(profile['id']) + ',options={{text="original",value="none"},{text="replacement",value=' + lua(profile['id']) + '}}},'
    data = 'return {name=' + lua(mod_id) + ',description="description",is_togglable=true,options={widgets={' + options + '}}}\n'
    (scripts / (mod_id + '_data.lua')).write_text(data, encoding='utf-8')
    localization = {
        'description': {'en': 'Local cosmetic replacement. Requires Custom Assets; restart after installation.', 'zh-cn': '客户端外观替换。需要 Custom Assets，安装后重启游戏。'},
        'first_person_arms': {'en': 'First-person arms', 'zh-cn': '第一人称手臂'},
        'skin_model': {'en': 'Weapon appearance', 'zh-cn': '武器外观'},
        'original': {'en': 'Original', 'zh-cn': '原版'},
        'replacement': {'en': 'Replacement', 'zh-cn': '替换模型'},
        'status_help': {'en': 'Show model replacement status'},
        'status_line': {'en': '%s | active %d | replaced %d | skipped %d | queued %d'},
        'refresh_hint': {'en': 'Use a fresh game session after installation.'},
        'no_adapted_weapons': {'en': 'This weapon has no adapted model.'},
    }
    text = 'return {' + ','.join('[' + lua(key) + ']={' + ','.join('[' + lua(lang) + ']=' + lua(value) for lang, value in values.items()) + '}' for key, values in localization.items()) + '}\n'
    (scripts / (mod_id + '_localization.lua')).write_text(text, encoding='utf-8')
    save_json(output / 'info.json', {'name': mod_id, 'version': '0.1.0', 'description': 'Source-profile cosmetic model replacement',
        'toolkit': 'https://github.com/Vionian/darktide-model-replacement', 'in_game_visual_verified': False})
    (output / 'INSTALL.txt').write_text(
        'Install DML, DMF and Custom Assets from their original publishers. Close the game.\n'
        'Copy this folder into <game>/mods; put CustomAssets before this mod ID in mods/mod_load_order.txt.\n'
        'Back up the affected registration files, bundle database and planned bundle/stream writes, then run the Custom Assets patcher.\n'
        'Confirm a final no-change dry run, restart the game and check first/third person, equipment and lifecycle transitions.\n'
        'Baseline character runtime covers live actors. Menu portraits and previews require an additional reviewed integration.\n', encoding='utf-8')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate')
    parser.add_argument('--output', required=True)
    parser.add_argument('--mod-id', required=True)
    args = parser.parse_args()
    try:
        print(scaffold(args.candidate, args.output, args.mod_id))
    except (ValueError, OSError) as error:
        parser.exit(1, 'ERROR: ' + str(error) + '\n')
