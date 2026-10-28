"""Integrate audited third-batch resources into the workspace only."""
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import integrate_endfield_batch as integration
from endfield_wave3 import PROFILES
keys = [k for k in sys.argv[1:] if not k.startswith('--')] or list(PROFILES)
assert all(k in PROFILES for k in keys), keys
integration.PROFILES = {k: (PROFILES[k]['name'], PROFILES[k]['provider']) for k in keys}
integration.main()
