"""Diagnostic only: compare complete sleeve without the FP cuff warp.

This preview intentionally differs from the compiled candidate and cannot be
used as deployment evidence. Original textures and existing serialized rig
remain the reference; no candidate or installed files are modified.
"""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import costume_cuff_fit
costume_cuff_fit.apply=lambda *args,**kwargs:None
path=HERE/'preview_roshia_native.py';source=path.read_text(encoding='utf8')
anchor='if args.asset_dir and not args.serialized_geometry:'
assert anchor in source
source=source.replace(anchor,"built_unit = builder.unit_dt.UnitResourceDT(builder.Cursor(str(args.asset_dir / (args.asset_prefix + '.unit'))))\nif False: # diagnostic geometry intentionally differs from compiled sleeve warp")
source=source.replace('scene.render.resolution_x = 1200','scene.render.resolution_x = 720').replace('scene.render.resolution_y = 1400','scene.render.resolution_y = 840').replace('scene.eevee.taa_render_samples = 128','scene.eevee.taa_render_samples = 32')
exec(compile(source,str(path),'exec'),{'__name__':'__main__','__file__':str(path)})
