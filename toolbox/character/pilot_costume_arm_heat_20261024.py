from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import build_roshia_native as b
from build_new_skin import configure
tag='endministrator_devil';configure(b,tag)
folder=HERE/'hand_repair_20261024/pilot_devil_heat';folder.mkdir(exist_ok=True)
b.OUTPUT=folder/'Custom';b.OUTPUT.mkdir(exist_ok=True)
b.HAND_AUTHORING_OUTPUT=folder/'native';b.HAND_AUTHORING_OUTPUT.mkdir(exist_ok=True)
prepare=b.prepare_source
def with_heat(mesh,arm):
    prepare(mesh,arm)
    from costume_arm_heat_weights import apply
    apply(b,mesh,arm)
b.prepare_source=with_heat
sys.argv=[sys.argv[0],'--','--asset-prefix',tag,'--source-blend',str(b.SOURCE_BLEND),
    '--resource-root',b.RESOURCE_ROOT,'--mesh-object',b.MESH_OBJECT_NAME,
    '--armature-object',b.ARMATURE_OBJECT_NAME,'--scale',str(b.SCALE),'--output-dir',str(b.OUTPUT),
    '--runtime-config-output',str(b.OUTPUT/(tag+'_jiggle_bones.lua'))]
b.main()
