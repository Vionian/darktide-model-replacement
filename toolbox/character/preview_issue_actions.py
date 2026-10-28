"""Render compiled issue candidates with exported production-Lua poses."""
from pathlib import Path
import concurrent.futures, json, sys
from validate_issue_repairs import run_command, OUT
from skins_sources import OUT as SKINS

def render(tag):
    folder = OUT / ('action_' + tag)
    folder.mkdir(exist_ok=True)
    source = SKINS / tag
    common = ['--skin-profile', tag]
    if tag.startswith('endministrator_devil'):
        run_command(folder, 'run', 'preview_roshia_native.py', common +
                    ['--asset-dir', source / 'Custom' / tag, '--runtime-pose',
                     source / 'body_run_frame_05_pose.json', '--output-dir', folder / 'run',
                     '--views', 'front', 'back'])
    if tag == 'aitela_hiro':
        run_command(folder, 'head', 'preview_roshia_native.py', common +
                    ['--asset-dir', source / 'Custom' / tag, '--runtime-pose',
                     source / 'body_head_turn_pose.json', '--output-dir', folder / 'head',
                     '--focus-region', 'upper-body', '--views', 'front', 'back'])
    run_command(folder, 'reload', 'preview_roshia_native.py', common +
                ['--asset-dir', source / 'Custom' / (tag + '_arms'), '--first-person',
                 '--individual-hands', '--runtime-pose', source / 'arms_reload_pose.json',
                 '--output-dir', folder / 'reload', '--views', 'front'])
    return dict(profile=tag, compiled_action_previews=True, in_game_verified=False)

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(render, sys.argv[1:]))
    (OUT / 'action_preview_results.json').write_text(json.dumps(results, indent=2), encoding='utf8')
    print(json.dumps(results), flush=True)
