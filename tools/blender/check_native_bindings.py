"""Exercise the real SDK reader against compiled synthetic UNIT corruption."""
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from worker import enable_sdk
from native_audit import material_bindings

job = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
sdk = enable_sdk(job)
checked = []
for unit in sorted(Path(job['output']).glob('*-candidate/compiled/*/*.unit')):
    original = unit.read_bytes()
    _, bindings = material_bindings(original, sdk)
    slot, identity = bindings[0]
    token = struct.pack('<IQ', slot, identity)
    if original.count(token) != 1:
        raise ValueError('Synthetic binding is not unique; update the fixture')
    damaged = original.replace(token, struct.pack('<IQ', slot, 0), 1)
    try:
        material_bindings(damaged, sdk)
    except ValueError as error:
        if 'zero native material' not in str(error):
            raise
    else:
        raise ValueError('Native reader accepted a zero material resource ID')
    if unit.read_bytes() != original:
        raise ValueError('Regression fixture modified the original compiled UNIT')
    checked.append(unit.name)
if len(checked) != 3:
    raise ValueError('Expected synthetic character body, arms and weapon')
print('NATIVE_BINDING_CORRUPTION_REJECTED', checked)
