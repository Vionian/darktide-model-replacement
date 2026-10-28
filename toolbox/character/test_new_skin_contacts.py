"""Run the existing production driver stress suite with an outfit's real rig."""
from pathlib import Path
import sys,json
HERE=Path(__file__).parent;sys.path.insert(0,str(HERE))
from skins_sources import OUT
from integrate_new_skins import PROVIDERS
tag=sys.argv[1]
base=json.loads((OUT/tag/'conversion.json').read_text(encoding='utf8'))['base']
script=HERE/'test_roshia_contacts.py'
code=script.read_text(encoding='utf8').replace('RoshiaReplacement',PROVIDERS[base])
code=code.replace("/roshia_jiggle.lua'","/"+base+"_jiggle.lua'")
for a,z in [("'roshia'",repr(tag)),("'roshia_arms'",repr(tag+'_arms')),
    ('Custom/roshia_proportion_bones.json','Custom/'+tag+'_proportion_bones.json'),
    ('Custom/roshia_jiggle_bones.lua','Custom/'+tag+'_jiggle_bones.lua'),
    ('Custom/roshia_jiggle_bones.json','Custom/'+tag+'_jiggle_bones.json')]:code=code.replace(a,z)
sys.argv=[str(script),str(OUT/tag),*sys.argv[2:]]
exec(compile(code,str(script),'exec'),{'__name__':'__main__','__file__':str(script)})
