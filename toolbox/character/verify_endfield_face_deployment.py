"""Verify the face-only delivery against candidates and pre-change game files."""
import datetime
import hashlib
import json
import pathlib

from endfield_wave2 import PROFILES

HERE = pathlib.Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
BATCH = HERE / 'endfield_batch'
FACE = BATCH / 'face_refinement'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify():
    deployment = read(BATCH / 'wave2_deployment_latest.json')
    assert deployment['assets_only'], 'Face delivery must preserve runtime Lua'
    game = pathlib.Path(deployment['mod_root'])
    verified = []
    expected = set()
    for key in PROFILES:
        for asset in (key, key + '_arms'):
            candidate = BATCH / key / 'Custom' / asset
            manifest = read(candidate / 'build.json')
            for relative in [e['path'] for e in manifest['artifacts']] + ['build.json', 'compile_manifest.json']:
                resource = pathlib.Path('Custom') / asset / relative
                assert (candidate / relative).resolve().is_relative_to(candidate.resolve()), relative
                digest = sha(candidate / relative)
                assert sha(WORKSPACE / resource) == digest, ('workspace', str(resource))
                assert sha(game / resource) == digest, ('game', str(resource))
                expected.add(resource.as_posix())
    for row in deployment['files']:
        resource = pathlib.Path(row['path'])
        assert resource.parts[0] == 'Custom', row['path']
        assert sha(game / resource) == row['sha256'].lower(), row['path']
        verified.append(resource.as_posix())
    assert set(verified) == expected and len(verified) == len(expected)

    arms = read(FACE / 'deployed_arms_baseline.json')
    for key, files in arms.items():
        for relative, digest in files.items():
            assert sha(game / 'Custom' / (key + '_arms') / relative) == digest, (key, relative)
    runtime = read(FACE / 'deployed_runtime_baseline.json')
    for relative, digest in runtime.items():
        assert sha(game / relative) == digest, relative
    backup = pathlib.Path(deployment['backup'])
    assert (backup / 'patcher.log').is_file()
    dry_run = (backup / 'patcher_dry_run.log').read_text(encoding='utf-8-sig')
    assert 'no database change would be written' in dry_run, dry_run

    report = {
        'verified_at': datetime.datetime.now().astimezone().isoformat(),
        'game_mod': str(game),
        'profiles': list(PROFILES),
        'candidate_workspace_game_matching_files': len(verified),
        'first_person_baseline_files_unchanged': sum(map(len, arms.values())),
        'runtime_baseline_files_unchanged': len(runtime),
        'backup': str(backup),
        'patcher_completed': True,
        'patcher_final_dry_run_no_changes': True,
        'gameplay_verified': False,
    }
    (FACE / 'deployment_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    audit = read(FACE / 'face_refinement_audit.json')
    audit['deployment'] = report
    (FACE / 'face_refinement_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    print('FACE_DEPLOYMENT_VERIFIED', json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    verify()
