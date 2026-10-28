"""Regenerate public indexes from the archived source inventory."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / 'toolbox/inventory.json'
    items = json.loads(path.read_text(encoding='utf-8'))
    known = {x['path'] for x in items}
    for file in sorted((ROOT / 'toolbox/runtime').rglob('*.lua')):
        relative = file.relative_to(ROOT).as_posix()
        if relative not in known:
            items.append({'path': relative, 'source_project': file.relative_to(ROOT).parts[2],
                          'status': 'runtime reference: integrate and validate for the new profile'})
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# 完整工具索引', '',
             '可移植入口见 [工具说明](tools.md)。以下历史源码需按新模型重建输入，不能批量执行。', '',
             '| 文件 | 来源 | 状态 |', '| --- | --- | --- |']
    lines.extend(f"| [{x['path']}](../{x['path']}) | {x['source_project']} | {x['status']} |" for x in items)
    (ROOT / 'docs/toolbox-catalog.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    lines = ['# 知识库索引', '',
             '历史案例保留模型名和技术背景，不包含艺术资源。案例路径是线索，不是仓库随附输入。', '',
             '| 专题 | 文件 |', '| --- | --- |']
    for file in sorted((ROOT / 'skills/darktide-model-replacement/references').glob('*.md')):
        heading = next((s.lstrip('# ').strip() for s in file.read_text(encoding='utf-8').splitlines()
                        if s.startswith('# ')), file.stem)
        lines.append(f'| [{heading}](../{file.relative_to(ROOT).as_posix()}) | {file.name} |')
    (ROOT / 'docs/knowledge-index.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Indexed {len(items)} historical source files')


if __name__ == '__main__':
    main()
