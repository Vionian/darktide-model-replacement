"""Run established tools for batch three without changing batch-two reports."""
import pathlib
import sys
here = pathlib.Path(__file__).parent
sys.path.insert(0, str(here))
path = here / 'run_endfield_wave2.py'
text = path.read_text(encoding='utf8')
text = text.replace('from endfield_wave2 import PROFILES', 'from endfield_wave3 import PROFILES')
text = text.replace("'wave2_'", "'wave3_'")
exec(compile(text, str(path), 'exec'), {'__name__': '__main__', '__file__': str(path)})
