"""Compile synthetic body/arms and weapon candidates using only repository tools."""
import json
from pathlib import Path
import subprocess
import sys
import time

from darktide import CACHE, ROOT, load_config, save_json
from package_mod import package_candidate
from scaffold_mod import scaffold


def main():
    config = load_config()
    output = CACHE / 'smoke' / time.strftime('%Y%m%d-%H%M%S')
    output.mkdir(parents=True, exist_ok=False)
    job = dict(config, output=str(output))
    save_json(output / 'fixture-job.json', job)
    commands = [[config['blender'], '--background', '--factory-startup', '--python-exit-code', '1',
                 '--python', str(ROOT / 'tools/blender/make_fixtures.py'), '--', str(output / 'fixture-job.json')]]
    profiles = {}
    for kind in ('character', 'weapon'):
        profile = json.loads((ROOT / 'profiles' / (kind + '.example.json')).read_text())
        profile['id'] = 'synthetic_' + kind
        if kind == 'weapon':
            profile['coordinate_frame_reviewed'] = True
            profile['alignment_evidence'] = 'Synthetic test prism authored in the native +Z blade frame; this is not a real weapon-fit preset.'
        save_json(output / (kind + '.json'), profile)
        profiles[kind] = profile
        commands.append([sys.executable, str(ROOT / 'tools/darktide.py'), 'inspect', str(output / (kind + '.blend')),
                         '--output', str(output / (kind + '-inspection'))])
        commands.append([sys.executable, str(ROOT / 'tools/darktide.py'), 'build', str(output / (kind + '.blend')),
                         '--profile', str(output / (kind + '.json')), '--output', str(output / (kind + '-candidate'))])
    commands.append([config['blender'], '--background', '--factory-startup', '--python-exit-code', '1',
                     '--python', str(ROOT / 'tools/blender/check_native_bindings.py'), '--', str(output / 'fixture-job.json')])
    for index, command in enumerate(commands):
        print('SMOKE_STAGE', index + 1, 'of', len(commands), flush=True)
        result = subprocess.run(command, capture_output=True, encoding='utf-8', errors='replace')
        log = result.stdout + result.stderr
        (output / f'stage-{index + 1}.log').write_text(log, encoding='utf-8')
        if result.returncode:
            print(log[-18000:])
            raise SystemExit(result.returncode)
    evidence = {}
    for kind in profiles:
        candidate = output / (kind + '-candidate')
        report = json.loads((candidate / 'build-report.json').read_text(encoding='utf-8'))
        runtime = scaffold(candidate, output / (kind + '-runtime'), 'Synthetic' + kind.title())
        archive = package_candidate(candidate, runtime, output / (kind + '-package'), ROOT)
        evidence[kind] = {
            'assets': report['assets'], 'native_audits_passed': report['native_audits_passed'],
            'in_game_visual_verified': False,
            'package_created': Path(archive).is_file(),
        }
    save_json(output / 'smoke-result.json', evidence)
    print('SMOKE_TEST_PASSED', json.dumps(evidence))
    print('LOCAL_EVIDENCE', output)


if __name__ == '__main__':
    main()
