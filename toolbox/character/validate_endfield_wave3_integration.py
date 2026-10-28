"""Validate workspace declarations, all class routes and candidate hashes."""
from pathlib import Path
HERE = Path(__file__).parent
path = HERE / 'validate_endfield_integration.py'
text = path.read_text(encoding='utf-8')
text = text.replace('from integrate_endfield_batch import PROFILES',
    'from endfield_wave3 import PROFILES as SELECTORS\nPROFILES={k:(p["name"],p["provider"])for k,p in SELECTORS.items()}')
text = text.replace('from lupa import LuaRuntime', 'from lupa.luajit21 import LuaRuntime')
text = text.replace('len(defs.models)==9', 'len(defs.models)==20')
text = text.replace('len(v.options)==9', 'len(v.options)==20')
text = text.replace("assert mod.should_replace(provider,cls.id,surface,'human')",
    "assert mod.should_replace(provider,cls.id,surface,'human')\n            assert mod.should_replace(provider,cls.id,surface,'cryptic')")
text = text.replace("'six_class_routes':True", "'six_class_routes':True,'cryptic_supported':True")
text = text.replace('endfield_batch/integration_audit.json', 'endfield_batch/wave3_integration_audit.json')
text = text.replace('local f,e=load(s)', 'local f,e=loadstring(s)')
exec(compile(text,str(path),'exec'), {'__name__':'__main__','__file__':str(path)})
