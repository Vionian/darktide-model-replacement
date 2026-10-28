"""Supplement the 23-pose audit with an isolated head yaw and tilt."""
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
wrapper = (HERE / 'test_new_skin_contacts.py').read_text(encoding='utf8')
injection = r'''
code = code.replace('        source_world=fk(dl,pars)\n',
    "        if case=='head_turn':\n            i=names['j_head']\n            dl[i][:3,:3]=dl[i][:3,:3]@R.from_euler('zyx',[45,12,0],degrees=True).as_matrix()\n        source_world=fk(dl,pars)\n", 1)
code = code.replace('contact_runtime_audit.json', 'head_turn_audit.json')
'''
wrapper = wrapper.replace('exec(compile(code', injection + '\nexec(compile(code')
sys.argv = [str(HERE / 'test_new_skin_contacts.py'), 'aitela_hiro', '--cases', 'head_turn']
exec(compile(wrapper, str(HERE / 'test_new_skin_contacts.py'), 'exec'),
     {'__name__': '__main__', '__file__': str(HERE / 'test_new_skin_contacts.py')})
