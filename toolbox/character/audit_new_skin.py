"""Reuse the established serialized geometry/bind audit for an outfit."""
from pathlib import Path
import sys
HERE=Path(__file__).parent;sys.path.insert(0,str(HERE))
from skins_sources import OUT
tag=sys.argv[sys.argv.index('--')+1]
script=HERE/'audit_roshia_hd2_adapt.py'
text=script.read_text(encoding='utf8')
text=text.replace('import build_roshia_native as b',
    'import build_roshia_native as b\nfrom build_new_skin import configure\nconfigure(b,'+repr(tag)+')')
for a,z in [("'roshia'",repr(tag)),("'roshia_arms'",repr(tag+'_arms')),('Custom/roshia_proportion_bones.json','Custom/'+tag+'_proportion_bones.json')]:text=text.replace(a,z)
sys.argv=[str(script),'--',str(OUT/tag)]
exec(compile(text,str(script),'exec'),{'__name__':'__main__','__file__':str(script)})
