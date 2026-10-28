import bpy,sys,json
from pathlib import Path
HERE=Path(__file__).parent;sys.path.insert(0,str(HERE))
from skins_sources import OUT
for folder in (OUT/'references').iterdir():
    meta=json.loads((folder/'source.json').read_text(encoding='utf8'))
    bpy.ops.wm.open_mainfile(filepath=meta['source'])
    arm=bpy.data.objects[meta['armature']]
    rows={}
    for bone in arm.data.bones:
        names=[bone.name]
        if hasattr(bone,'mmd_bone'):names.extend([bone.mmd_bone.name_j,bone.mmd_bone.name_e])
        rows[bone.name]=names
    (folder/'bone_aliases.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
    print('ALIASES',folder.name,len(rows),flush=True)
