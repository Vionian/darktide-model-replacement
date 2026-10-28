"""Run the established resource/Lua/MMR probes with a selected source profile.

Preserves the original audit implementations and assertions; only resource,
provider and source selectors vary. Run Blender for assets/mmr, Python for lua.
"""
import argparse,pathlib,sys
here=pathlib.Path(__file__).parent
sys.path.insert(0,str(here))
args=sys.argv[sys.argv.index('--')+1:] if '--'in sys.argv else sys.argv[1:]
mode,key=args[:2]
options=argparse.ArgumentParser()
options.add_argument('--output',type=pathlib.Path)
options.add_argument('--cases',nargs='+')
opts=options.parse_args(args[2:])
providers={'lizhiyan':'LizhiyanReplacement','endministrator_f':'EndministratorReplacement',
           'si':'SiReplacement','si_ink_mist':'SiReplacement','si_short_skirt':'SiReplacement',
           'si_lolita':'SiReplacement','typhoea':'TyphoeaReplacement'}
from endfield_wave2 import PROFILES
providers.update({k:p['provider']for k,p in PROFILES.items()})
from endfield_wave3 import PROFILES as WAVE3
providers.update({k:p['provider']for k,p in WAVE3.items()})
script={'assets':'audit_roshia_hd2_adapt.py','lua':'test_roshia_contacts.py','mmr':'audit_roshia_source_hands.py'}[mode]
path=here/script
text=path.read_text(encoding='utf-8')
text=text.replace('.read_text()', ".read_text(encoding='utf-8')")
text=text.replace('RoshiaReplacement',providers[key])
# Keep shared implementation imports unchanged. Resource/config selectors,
# fixture keys and offline project labels are profile-specific.
for a,z in [("'roshia'",repr(key)),("'roshia_arms'",repr(key+'_arms')),
            ('Custom/roshia_', 'Custom/'+key+'_'),('/roshia_jiggle.lua','/'+key+'_jiggle.lua')]:
    text=text.replace(a,z)
if key.startswith('si_'):text=text.replace('/'+key+'_jiggle.lua','/si_jiggle.lua')
text=text.replace('roshia_source_hand_mmr.blend',key+'_source_hand_mmr.blend')
text=text.replace('Roshia_source_hands_MMR',key+'_source_hands_MMR')
if mode!='lua':
    text=text.replace('import build_roshia_native as b',
                      'import build_roshia_native as b\nfrom endfield_profiles import apply\napply(b,'+repr(key)+')'+
                      ('\nb.HAND_AUTHORING_OUTPUT=pathlib.Path('+repr(str(here/'endfield_batch'/key))+')'if mode=='mmr'else ''))
out=opts.output.resolve() if opts.output else here/'endfield_batch'/key
sys.argv=[str(path),str(out)] if mode=='lua' else [str(path),'--',str(out)]
if mode=='lua' and opts.cases:sys.argv+=['--cases']+opts.cases
exec(compile(text,str(path),'exec'),{'__name__':'__main__','__file__':str(path)})
