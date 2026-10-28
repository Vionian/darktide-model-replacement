"""Check publication files without reading ignored private data."""
import ast
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BINARY = {'.blend', '.blend1', '.fbx', '.pmx', '.pmd', '.unit', '.bones', '.material', '.texture',
          '.stream', '.dll', '.exe', '.zip', '.7z', '.rar', '.dmp', '.log', '.png', '.jpg', '.dds'}


def public_files(root=ROOT):
    result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                            cwd=root, check=True, capture_output=True)
    return sorted({root / name for name in result.stdout.decode('utf-8').split('\0') if name})


def validate(root=ROOT):
    errors = []
    files = public_files(root)
    for file in files:
        rel = file.relative_to(root).as_posix()
        if not file.is_file():
            errors.append(f'Missing staged file: {rel}')
            continue
        if file.suffix.lower() in BINARY or file.stat().st_size > 2_000_000:
            errors.append(f'Unexpected asset/binary/large file: {rel}')
            continue
        try:
            text = file.read_text(encoding='utf-8-sig')
        except UnicodeError:
            errors.append(f'Non-text public file: {rel}')
            continue
        if '\0' in text:
            errors.append(f'Binary data: {rel}')
        if file.suffix == '.py':
            try:
                ast.parse(text, filename=rel)
            except SyntaxError as error:
                errors.append(f'Python syntax: {rel}:{error.lineno}: {error.msg}')
        if file.suffix == '.json':
            try:
                json.loads(text)
            except ValueError as error:
                errors.append(f'JSON syntax: {rel}: {error}')
        private = [r'(?i)(?:[A-Z]:[/\\](?:Users[/\\][^/\\\s]+|SteamLibrary)|[A-Z]:[/\\]mod[/\\])',
                   r'(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}', r'(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]{24,}',
                   r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----']
        if any(re.search(pattern, text) for pattern in private):
            errors.append(f'Private path or credential pattern: {rel}')
        if file.suffix == '.md':
            for match in re.finditer(r'\]\(([^)]+)\)', text):
                link = match.group(1).strip().strip('<>')
                if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', link) or link.startswith('#'):
                    continue
                target = link.split('#')[0]
                if target and not (file.parent / target).exists():
                    errors.append(f'Broken Markdown link: {rel}: {target}')
    skill = root / 'skills/darktide-model-replacement/SKILL.md'
    text = skill.read_text(encoding='utf-8')
    if not text.startswith('---\n') or not re.search(r'^name: darktide-model-replacement$', text, re.M) or not re.search(r'^description: .+', text, re.M):
        errors.append('Skill frontmatter is incomplete')
    inventory = json.loads((root / 'toolbox/inventory.json').read_text(encoding='utf-8'))
    expected = {p.relative_to(root).as_posix() for p in (root / 'toolbox').rglob('*') if p.suffix in {'.py', '.lua'}}
    recorded = {x['path'] for x in inventory}
    if recorded != expected or len(recorded) != len(inventory):
        errors.append('Toolbox inventory is incomplete or duplicated')
    return files, errors


if __name__ == '__main__':
    files, errors = validate()
    for error in errors:
        print('ERROR:', error)
    print(f'Public files checked: {len(files)}; errors: {len(errors)}')
    raise SystemExit(bool(errors))
