"""Run the existing integration contract against the eight additional models."""
import pathlib,sys
HERE=pathlib.Path(__file__).parent
sys.path.insert(0,str(HERE))
path=HERE/'validate_endfield_integration.py'
text=path.read_text(encoding='utf-8')
text=text.replace('from integrate_endfield_batch import PROFILES',
    'from endfield_wave2 import PROFILES as SELECTORS\nPROFILES={k:(p["name"],p["provider"])for k,p in SELECTORS.items()}')
text=text.replace('len(defs.models)==9','len(defs.models)==17')
text=text.replace('len(v.options)==9','len(v.options)==17')
text=text.replace('endfield_batch/integration_audit.json','endfield_batch/wave2_integration_audit.json')
exec(compile(text,str(path),'exec'),{'__name__':'__main__','__file__':str(path)})
