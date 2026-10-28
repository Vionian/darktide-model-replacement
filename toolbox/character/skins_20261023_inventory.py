"""Inventory supplied outfit sources without altering the source folders."""
from pathlib import Path
from collections import Counter
import json
ROOT=Path(r'<SOURCE_ROOT>\Skins')
OUT=Path(__file__).parent/'skins_20261023'
OUT.mkdir(exist_ok=True)
rows=[]
for folder in sorted(p for p in ROOT.iterdir() if p.is_dir()):
    files=sorted(p for p in folder.rglob('*') if p.is_file())
    row=dict(name=folder.name,path=str(folder),
             extensions=dict(Counter(p.suffix.lower() for p in files)),
             files=[dict(path=str(p.relative_to(folder)),size=p.stat().st_size) for p in files])
    rows.append(row)
(OUT/'inventory.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
for row in rows:
    print(json.dumps(dict(name=row['name'],extensions=row['extensions'],
        ini=[p['path'] for p in row['files'] if p['path'].endswith('.ini')],
        previews=[p['path'] for p in row['files'] if p['path'].endswith('.png') and ('Buffer' not in p['path'] and 'Tex' not in p['path'])]),ensure_ascii=True))
