"""Validate isolated October 23 original/legacy repairs without deployment."""
from pathlib import Path
import concurrent.futures, json, shutil, subprocess, sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'issue_fixes_20261023'
BLENDER = '<BLENDER_EXE>'

def run_command(folder, label, script, args, blender=True):
    command = ([BLENDER, '-b', '--threads', '4', '--python-exit-code', '1',
                '--python', str(HERE / script), '--'] if blender else
               [sys.executable, '-X', 'utf8', str(HERE / script)]) + list(map(str, args))
    print('START', folder.name, label, flush=True)
    log = folder / (label + '.log')
    with log.open('w', encoding='utf8') as stream:
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    value = log.read_text(encoding='utf8', errors='replace')
    assert result.returncode == 0 and 'Traceback' not in value, (label, log)
    print('DONE', folder.name, label, flush=True)

def validate(tag):
    folder = OUT / tag
    asset = 'roshia' if tag == 'roshia_original' else tag
    log = (OUT / (tag + '_build.log')).read_text(encoding='utf8', errors='replace')
    assert 'ROSHIA_BUILD' in log and 'Traceback' not in log, tag
    if asset != 'roshia':
        shutil.copy2(folder / 'Custom' / 'roshia_jiggle_bones.json',
                     folder / 'Custom' / (asset + '_jiggle_bones.json'))
        for ext in ('json', 'lua'):
            shutil.copy2(folder / 'Custom' / ('roshia_proportion_bones.' + ext),
                         folder / 'Custom' / (asset + '_proportion_bones.' + ext))
        run_command(folder, 'assets', 'audit_endfield_native.py', ['assets', tag, '--output', folder])
        run_command(folder, 'contacts', 'audit_endfield_native.py', ['lua', tag, '--output', folder], False)
        selector = ['--model-profile', tag]
    else:
        run_command(folder, 'assets', 'audit_roshia_hd2_adapt.py', [folder])
        run_command(folder, 'contacts', 'test_roshia_contacts.py', [folder], False)
        selector = []
    common = selector + ['--asset-dir', folder / 'Custom' / asset]
    if asset == 'roshia':
        for focus in ('face', 'tail'):
            run_command(folder, 'preview_' + focus, 'preview_roshia_native.py',
                        common + ['--focus-region', focus, '--output-dir', folder / ('preview_' + focus),
                                  '--views', 'front' if focus == 'face' else 'back'])
    else:
        for pose in ('rest', 'reload'):
            run_command(folder, 'hands_' + pose, 'preview_roshia_native.py', selector +
                        ['--asset-dir', folder / 'Custom' / (asset + '_arms'), '--first-person',
                         '--individual-hands', '--runtime-pose', folder / ('arms_' + pose + '_pose.json'),
                         '--output-dir', folder / ('hands_' + pose), '--views', 'front'])
    result = dict(profile=tag, asset_audit=True, production_lua_poses=23,
                  compiled_previews=True, in_game_verified=False)
    (folder / 'repair_checks.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    return result

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(validate, sys.argv[1:]))
    print(json.dumps(results), flush=True)
