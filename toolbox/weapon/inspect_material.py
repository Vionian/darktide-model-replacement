from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,'<CHARACTER_WORKSPACE>/tools/model-work')
import build_roshia_native as b
b.TEMPLATE=ROOT/'WeaponModelReplacement/Custom/khravengger'
material=b.MaterialResourceDT(b.Cursor(str(b.TEMPLATE/'khravengger_material_0.material')))
for name,m in material.materials:
    print('MATERIAL',name)
    print('VARIABLES',json.dumps(m.get_variables(),indent=2,default=str))
    print('FIELDS',list(vars(m)))
