"""Reuse read-only source inspection, scoped to the third character batch."""
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from endfield_wave3 import PROFILES

path = pathlib.Path(__file__).with_name('inspect_endfield_wave2.py')
text = path.read_text(encoding='utf-8')
text = text.replace('from endfield_wave2 import PROFILES',
                    'from endfield_wave3 import PROFILES')
text = text.replace('wave2_source_inspection.json', 'wave3_source_inspection.json')
text = text.replace('WAVE2_', 'WAVE3_')
exec(compile(text, str(path), 'exec'), {'__name__': '__main__', '__file__': str(path)})
