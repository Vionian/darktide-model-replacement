"""Package a reviewed runtime with a verified isolated candidate; never install it."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

from darktide import inside, save_json, validate_manifest


def package_candidate(candidate, runtime, output, repository):
    candidate, runtime, output = candidate.resolve(), runtime.resolve(), output.resolve()
    report = json.loads((candidate / 'build-report.json').read_text(encoding='utf-8'))
    if not (candidate / 'native-audit.json').is_file() or not report.get('native_audits_passed'):
        raise ValueError('Native resource audit is required before packaging')
    manifests = sorted(candidate.glob('compiled/*/build.json'))
    if not manifests or {p.parent.name for p in manifests} != set(report.get('assets', [])):
        raise ValueError('Compiled asset folders do not match the build report')
    audits = json.loads((candidate / 'native-audit.json').read_text(encoding='utf-8'))
    if {a['asset'] for a in audits} != set(report['assets']) or not all(
        a.get('units') and all(u.get('zero_material_ids') == 0 and u.get('all_bound_materials_in_manifest')
                              for u in a['units']) for a in audits):
        raise ValueError('Native material audit evidence is incomplete')
    descriptors = list(runtime.glob('*.mod'))
    if len(descriptors) != 1:
        raise ValueError('--runtime must be a reviewed mod directory containing one root .mod descriptor')
    mod_id = descriptors[0].stem
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', mod_id):
        raise ValueError('Mod folder ID must contain only ASCII letters, digits and underscores')
    if output.exists():
        raise ValueError('Choose a fresh distribution directory')
    for entry in runtime.rglob('*'):
        if entry.is_symlink() or (entry.is_file() and (entry.suffix.lower() not in {'.lua', '.mod', '.json', '.txt', '.md'}
                or entry.name in {'job.local.json', 'config.json'})):
            raise ValueError(f'Unreviewed source, binary or private file in runtime: {entry.name}')
    for manifest in manifests:
        validate_manifest(manifest)
    package = output / mod_id
    shutil.copytree(runtime, package)
    for manifest in manifests:
        asset = package / 'Custom' / manifest.parent.name
        asset.mkdir(parents=True, exist_ok=True)
        data = json.loads(manifest.read_text(encoding='utf-8-sig'))
        paths = {'build.json'}
        for entry in data['resources']:
            paths.add(entry['file']['path'])
            if entry.get('stream'):
                paths.add(entry['stream']['file']['path'])
        paths.update(entry['path'] for entry in data.get('artifacts', []))
        for relative in paths:
            src = inside(manifest.parent, relative)
            dst = inside(asset, relative)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    save_json(package / 'build-evidence.json', {
        'source_sha256': report['source_sha256'],
        'profile': {key: report['profile'][key] for key in ('id', 'kind', 'target_templates', 'attachment_prefix') if key in report['profile']},
        'native_audits_passed': True, 'in_game_visual_verified': report.get('in_game_visual_verified', False),
        'source_hand_mmr_executed': report.get('source_hand_mmr_executed', False),
    })
    hashes = {str(f.relative_to(package)).replace('\\', '/'): hashlib.sha256(f.read_bytes()).hexdigest()
              for f in package.rglob('*') if f.is_file()}
    save_json(package / 'SHA256SUMS.json', hashes)
    archive = output / (mod_id + '.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as target:
        for file in sorted(package.rglob('*')):
            if file.is_file():
                target.write(file, file.relative_to(output))
    return str(archive)
