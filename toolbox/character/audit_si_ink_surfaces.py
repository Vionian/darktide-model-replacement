"""Inspect real restored weights and serialized skin palettes for outfit regressions."""
import json,re,sys
from pathlib import Path
import numpy as np

HERE=Path(__file__).parent
sys.path.insert(0,str(HERE))
WORK=HERE/'si_ink_mist'
OUT=HERE/'endfield_batch/si_ink_mist'
data=np.load(WORK/'restored_meshes.npz')
conversion=json.loads((WORK/'conversion.json').read_text(encoding='utf8'))
names=data['group_names']
hair=np.array([bool(re.search(r'hair|ear_',n,re.I)) for n in names])
dynamic=np.array([bool(re.search(r'hair|ear_|bow|tail|sleeve|cloth|tassel|裙|ribbon|cloud|bracelet|錘|dummy|shadow',n,re.I)) for n in names])
report={'source_hair_contamination_removed':0,'restored_surfaces':[]}
assert conversion['excluded_white_stocking_draw']==[20472,312024]
assert all(r['index_start']!=312024 for r in conversion['draws'])
assert len(conversion['hand_palette_correspondence'])==36
assert sum(r['triangles'] for r in conversion['draws'] if r['component'] in (9,11))==1868
for i,row in enumerate(conversion['draws']):
    assert row['index_start']!=185049,'Duplicate head/hair draw returned'
    ids=data[f'{i}_indices'];w=data[f'{i}_weights'];p=data[f'{i}_positions']
    assert np.max(abs(w.sum(1)-1))<2e-6
    hm=(w*hair[ids]).sum(1)
    assert hm.max()<1e-7,(i,'Hair influences on outfit or skin')
    if row['component']==5:
        assert (w*dynamic[ids]).sum(1).max()<1e-7
        assert row['normal']==17 and row['packed'] is None
    elif row['component']==3:
        assert not row['alpha'],'Physical garment returned to unsupported Alpha provider'
        assert row['geometric_cutout']['native_provider']=='substance_basic'
    else:
        assert row['component'] in (9,11) and row['diffuse']==1009 and not row['alpha']
        assert row['ink_strokes']['width_factor_range']==[.12,.22]
        assert (w*(names[ids]=='上半身2')).sum(1).min()>.99999
    chest=(abs(p[:,0])<=.15)&(p[:,2]>=1.08)&(p[:,2]<=1.32)
    if np.any(chest):
        chest_mass=(w*(names[ids]=='上半身2')).sum(1)
        assert chest_mass[chest].min()>.99999,(i,'Bodice no longer shares chest anchor')
    report['source_hair_contamination_removed']+=row['removed_hair_influence_vertices']
    report['restored_surfaces'].append({'draw':i,'component':row['component'],
        'hair_weight_max':float(hm.max()),'fixed_bodice_vertices':row['fitted_bodice_vertices']})

# Run this section inside Blender so the exact production unit parser is used.
import bpy
import build_roshia_native as b
from endfield_profiles import apply
apply(b,'si_ink_mist')
bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
mesh=bpy.data.objects[b.MESH_OBJECT_NAME]
assert sum(p.material_index==7 for p in mesh.data.polygons)==0, 'Original blue glove surface returned'
hair_mat=mesh.data.materials.get('发')
assert hair_mat.get('ink_mist_reference_hair')
assert hair_mat.node_tree.nodes['mmd_base_tex'].image.filepath.endswith('InkMist_hair_reference_D.png')
width,height,hair_pixels,_=b.image_pixels_for(hair_mat)
assert width==2048 and height==2048, 'Hair diffuse fell back to a constant'
assert np.std(hair_pixels[:,:,:3])>.08, 'Hair diffuse lost authored color detail'
report['reference_variant']={'green_hair':True,'blue_gloves_removed':True,'white_stockings_removed':True,
    'bare_hands':'continuous C5 geometry; original Si posed skin field and original-source MMR'}
unit=b.unit_dt.UnitResourceDT(b.Cursor(str(OUT/'Custom/si_ink_mist/si_ink_mist.unit')))
native_names=b.named_node_map(unit,b.BonesResourceDT(b.Cursor(str(OUT/'Custom/si_ink_mist/si_ink_mist_bones.bones'))))
hair_palettes=[palette for palette,node in enumerate(unit.skins[0].node_indices)
    if node in {v for n,v in native_names.items() if n.startswith('qianxia_hair_')}]
# Read each geometry's real material from the serialized slot -> resource map.
material_by_slot={slot.ID:resource.ID for slot,resource in unit.materials}
index_by_resource={b.hash64(f'content/mods/si_ink_mist/si_ink_mist_material_{i}'):i
    for i in range(len(mesh.data.materials))}
records=[]
import struct
report['garment_material_providers']={}
for prefix in ('si_ink_mist','si_ink_mist_arms'):
    folder=OUT/'Custom'/prefix
    manifest=json.loads((folder/'build.json').read_text(encoding='utf8'))
    checks=[]
    for i,mat in enumerate(mesh.data.materials):
        if not mat.name.startswith('InkMist_'):continue
        resource=f'content/mods/si_ink_mist/{prefix}_material_{i}'
        entries=[r for r in manifest['artifacts']if r.get('resource',{}).get('name')==resource and r.get('role')=='stream']
        if not entries:continue
        payload=(folder/entries[0]['path']).read_bytes();offset=struct.unpack_from('<I',payload,4)[0]
        assert struct.unpack_from('<Q',payload,offset+4)[0]==b.hash64('content/parent_materials/substance_basic'),mat.name
        assert (folder/f'{prefix}_material_{i}_bc.texture').is_file(),mat.name
        checks.append({'material':mat.name,'provider':'substance_basic','channel':'bc'})
    assert checks,(prefix,'No outfit material exported')
    report['garment_material_providers'][prefix]=checks
for slot,geo in enumerate(unit.mesh_geometries):
    material_hash=material_by_slot[b.IDString32.from_str(f'si_ink_mist_slot_{slot:02d}').ID]
    mi=index_by_resource[material_hash];mat=mesh.data.materials[mi]
    if 'ink_mist_diffuse'not in mat and mat.name!='肌':continue
    indices=np.frombuffer(geo.streams[5].vertex_data,np.uint8).reshape(-1,4)
    weights=np.frombuffer(geo.streams[4].vertex_data,'<f2').reshape(-1,4).astype(float)
    mass=np.where(np.isin(indices,hair_palettes),weights,0).sum(1)
    assert mass.max()<1e-7,mat.name
    records.append({'material':mat.name,'hair_palette_weight_max':float(mass.max())})
report['compiled_outfit_skin_checks']=records
assert records
report['native_resource_check']=str(OUT/'Custom/si_ink_mist/si_ink_mist.unit')
report['physical_garments_use_opaque_native_provider']=True
report['synthetic_hair_sway_skin_displacement_m']=0.0
report['scope']='Zero skin palette influence guarantees no deformation from hair-only motion; game lighting/full animations remain user validation.'
(WORK/'surface_fix_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('SI_INK_SURFACE_AUDIT',json.dumps({k:v for k,v in report.items() if not isinstance(v,list)},ensure_ascii=False))
