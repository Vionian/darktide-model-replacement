"""Reuse audited provider lifecycle while preserving existing character choices."""
import sys
import integrate_endfield_batch as integration
from endfield_wave2 import PROFILES
keys=[k for k in sys.argv[1:]if not k.startswith('--')]or list(PROFILES)
integration.PROFILES={k:(PROFILES[k]['name'],PROFILES[k]['provider'])for k in keys}
integration.main()
