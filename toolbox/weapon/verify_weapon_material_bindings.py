"""Blender native-reader regression for the 0.2.5 magenta weapon failure."""
from pathlib import Path
import sys,json,struct,hashlib
ROOT=Path(__file__).resolve().parents[1]
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
MOD=Path(args[0]) if args else ROOT/'WeaponModelReplacement'
sys.path.insert(0,'<CHARACTER_WORKSPACE>/tools/model-work')
import build_roshia_native as b
from bitsquid.murmur.murmurhash64 import hash64
ASSET=MOD/'Custom/khravengger'
manifest=json.loads((ASSET/'build.json').read_text())
resources={(r['key']['type'],r['key']['name']):r for r in manifest['resources']}
prefix='content/mods/weapon_model_replacement/'

def material_table(path):
    info=b.read_unit_offsets(path)
    entries=[struct.unpack_from('<IQ',info['raw'],info['materials_offset']+i*12)
             for i in range(info['material_count'])]
    used={str(slot).upper() for g in info['geometries'] for slot in g.materials}
    return info,entries,used

report={}
for name in ('langzhifei','khravengger'):
    slots={'ice_cover_'+c:prefix+'ice_cover_'+c for c in ('r','g','b')}
    slots[name+'_pbr']=prefix+name+'_material_0'
    expected={hash64(slot)>>32:hash64(resource) for slot,resource in slots.items()}
    path=ASSET/(name+'.unit')
    info,entries,used=material_table(path)
    assert len(entries)==len(dict(entries))==4,(name,entries)
    assert all(resource for _,resource in entries),'Null material binding in '+name
    assert dict(entries)==expected,(name,entries,expected)
    assert used=={f'{slot:08X}' for slot in expected},(name,used)
    unit=resources[('unit',prefix+name)]
    assert {d['name'] for d in unit['dependencies'] if d['type']=='material'}==set(slots.values())
    for resource in slots.values():
        entry=resources[('material',resource)]
        assert struct.unpack_from('<QQ',(ASSET/entry['file']['path']).read_bytes())==(
            hash64('material'),hash64(resource))
    report[name]={'material_slots':len(entries),'mesh_material_slots_resolved':True,
        'zero_resource_ids':0,'resources':slots,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    if name=='langzhifei':
        backup=Path((ROOT/'build/current_material_fix_backup.txt').read_text(encoding='utf-8').strip())
        old_info,old_entries,_=material_table(backup/'WeaponModelReplacement/Custom/khravengger/langzhifei.unit')
        assert len(old_entries)==4 and all(v==0 for _,v in old_entries),old_entries
        old,new=old_info['raw'],info['raw']
        # 0.2.8 deliberately replaces full-blade cover geometry with edge
        # ribbons. Exact base geometry is checked by verify_blade_edge.py.
        assert {slot for slot,_ in old_entries}==set(expected)
        report[name].update({'old_failure_reproduced':True,'old_zero_resource_ids':4,
            'all_current_resource_ids_match_manifest':True,
            'base_pose_verification':'build/blade_edge/geometry_audit.json'})
report['in_game_visual_verified']=False
out=ROOT/'build/wolf_material';out.mkdir(exist_ok=True)
(out/'native_binding_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('NATIVE_WEAPON_MATERIAL_BINDINGS_OK',json.dumps(report))
