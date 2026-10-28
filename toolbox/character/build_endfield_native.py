import pathlib, sys
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from endfield_profiles import apply, PROFILES
args=sys.argv[sys.argv.index('--')+1:]
key=args.pop(0)
apply(b,key)
out=b.ROOT/'tools/model-work/endfield_batch'/key/'Custom'
b.OUTPUT=out
b.HAND_AUTHORING_OUTPUT=out.parent
out.mkdir(parents=True,exist_ok=True)
b.HAND_AUTHORING_OUTPUT.mkdir(parents=True,exist_ok=True)
sys.argv=[sys.argv[0],'--','--asset-prefix',key,'--source-blend',str(b.SOURCE_BLEND),
          '--resource-root',b.RESOURCE_ROOT,'--mesh-object',b.MESH_OBJECT_NAME,
          '--armature-object',b.ARMATURE_OBJECT_NAME,'--scale',str(b.SCALE),
          '--output-dir',str(out),'--runtime-config-output',str(out/(key+'_jiggle_bones.lua'))]+args
b.main()
for suffix in ('proportion_bones.lua','proportion_bones.json','jiggle_bones.json'):
    f=b.OUTPUT/('roshia_'+suffix)
    if f.exists():f.replace(b.OUTPUT/(key+'_'+suffix))
print('ENDFIELD_BUILD_DONE',key)
