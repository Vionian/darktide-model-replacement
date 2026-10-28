from collections import Counter
import json
from skins_sources import OUT,SOURCES,source
from efmi_draws import Reader
for key in SOURCES:
    if key=='si_ink_wash':continue
    row=source(key);r=Reader(row['ini']);r.collect()
    print('\nSOURCE',key,'DRAW SECTIONS',dict(Counter(d['section'] for d in r.draws)))
    for name,lines in r.blocks.items():
        if any(l.split('=',1)[0].strip().lower() in ('drawindexed','drawindexedinstanced')for l in lines):
            if key=='roshia_lolita':print('DRAW_NAME',name)
    print('KEYS',[(n,lines[:9])for n,lines in r.blocks.items() if n.startswith('Key') and not any(x in n.lower()for x in ('hide','menu','ui'))][:12])
    for d in r.draws[:26]:
        paths={k:str(r.path(v).relative_to(r.root))for k,v in d['bindings'].items()if r.path(v)and (k=='ib' or 'diffuse'in k or k.startswith('ps-t'))}
        print('DRAW',d['section'],d['count'],d['start'],json.dumps(paths,ensure_ascii=True))
