"""Read-only material isolation of the actual compiled first-person unit."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
path=HERE/'preview_roshia_native.py'
source=path.read_text(encoding='utf8')
anchor='parser.add_argument("--diagnostic-solid"'
assert anchor in source
source=source.replace(anchor,'parser.add_argument("--only-materials",type=int,nargs="+")\nparser.add_argument("--only-material-names",nargs="+")\n'+anchor,1)
anchor='for geometry in geometries:\n'
assert anchor in source
source=source.replace(anchor,anchor+'    if args.only_materials and geometry["material_index"] not in args.only_materials:continue\n    if args.only_material_names and mesh.data.materials[geometry["material_index"]].name not in args.only_material_names:continue\n',1)
source=source.replace('scene.render.resolution_x = 1200','scene.render.resolution_x = 720').replace('scene.render.resolution_y = 1400','scene.render.resolution_y = 840').replace('scene.eevee.taa_render_samples = 128','scene.eevee.taa_render_samples = 32')
exec(compile(source,str(path),'exec'),{'__name__':'__main__','__file__':str(path)})
