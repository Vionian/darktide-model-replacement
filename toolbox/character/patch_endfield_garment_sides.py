"""Add missing authored reverse cloth faces to existing serialized body assets.

Preserves every original front vertex/UV/weight byte and the entire serialized
skin/scene/material suffix. No hand fitting, texture rebake or rig rebuild.
"""
import argparse
import gc
import hashlib
import json
import pathlib
import re
import shutil
import struct
import sys

import bpy
import numpy as np

sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from endfield_profiles import PROFILES
from native_garment_sides import authored_two_sided_garment,from_parsed,triangle_keys,append_reverse

parser=argparse.ArgumentParser()
parser.add_argument('--output',type=pathlib.Path,required=True)
parser.add_argument('--perlica-custom',type=pathlib.Path,required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
args.output.mkdir(parents=True,exist_ok=True)
inspection=json.loads((b.ROOT/'tools/model-work/endfield_batch/weights.json').read_text(encoding='utf-8'))
report={'scope':'Authored two-sided opaque garment surfaces; original fronts and skeleton retained',
        'assets':{},'gameplay_verified':False}
for key,profile in PROFILES.items():
    source=pathlib.Path(profile.get('source',pathlib.Path(r'<SOURCE_ROOT>\Rossia')/(profile['name']+'.blend')))
    bpy.ops.wm.open_mainfile(filepath=str(source))
    mesh=bpy.data.objects[inspection[profile['name']].get('mesh',profile['name']+'_mesh')]
    folder=(args.perlica_custom if key=='perlica' else b.ROOT/'Custom')/key
    if not (folder/(key+'.unit')).exists():continue
    manifest=json.loads((folder/'build.json').read_text(encoding='utf-8'))
    material_names={b.hash64(a['resource']['name']):a['resource']['name'] for a in manifest['artifacts']
                    if a['resource']['type']=='material' and a['role']=='primary'}
    alpha_indices={int(m.group(1)) for a in manifest['artifacts']
                   if a['resource']['type']=='texture' and (m:=re.search(r'_material_(\d+)_bca$',a['resource']['name']))}
    selected={i:mat.name for i,mat in enumerate(mesh.data.materials)
              if authored_two_sided_garment(mat) and i not in alpha_indices}
    unit_file=folder/(key+'.unit')
    unit=b.unit_dt.UnitResourceDT(b.Cursor(str(unit_file)))
    info=b.read_unit_offsets(unit_file)
    resource_by_slot={s.ID:r.ID for s,r in unit.materials}
    geometries=[];by_material={}
    for i,geo in enumerate(unit.mesh_geometries):
        resource=material_names[resource_by_slot[geo.materials[0].ID]]
        index=int(re.search(r'_material_(\d+)$',resource).group(1))
        g=from_parsed(b,geo,index);geometries.append(g)
        if index in selected:by_material.setdefault(index,[]).append(i)
    changed={};original_keys={}
    for material,ids in by_material.items():
        keypairs={i:triangle_keys(geometries[i]) for i in ids}
        known=set(k for direct,_ in keypairs.values() for k in direct)
        for i in ids:
            direct,reverse=keypairs[i]
            missing=np.array([j for j,k in enumerate(reverse) if k not in known],dtype=np.int64)
            if len(missing):
                original_keys[i]=direct
                changed[i]=int(len(missing))
                geometries[i]=append_reverse(b,geometries[i],missing)
    row={'source':str(source),'selected_materials':selected,'added_triangles':sum(changed.values()),
         'changed_geometry_count':len(changed),'original_unit_sha256':hashlib.sha256(info['raw']).hexdigest()}
    report['assets'][key]=row
    if not changed:
        row['status']='already double-sided or no selected garment';continue
    # Re-serialize just the geometry block. The unchanged suffix includes all
    # inverse binds, raw local TRS, node names/parents and material resources.
    c=b.Cursor(str(unit_file));c.seek(info['geometry_start']);parts=[]
    for i in range(len(geometries)):
        start=c.tell();b.mesh_geometry.MeshGeometryDT(c);end=c.tell()
        parts.append(b.serialize_geometry(geometries[i]) if i in changed else info['raw'][start:end])
    blob=b''.join(parts)
    output=bytearray(info['raw'][:info['geometry_start']]+blob+info['raw'][info['geometry_end']:])
    struct.pack_into('<I',output,29,len(output)-b.unit_dt.HEADER_SIZE)
    destination=args.output/'Custom'/key
    shutil.copytree(folder,destination,dirs_exist_ok=True)
    target=destination/(key+'.unit');target.write_bytes(output)
    reread=b.read_unit_offsets(target)
    assert reread['raw'][reread['geometry_end']:]==info['raw'][info['geometry_end']:]
    rebuilt=b.unit_dt.UnitResourceDT(b.Cursor(str(target)))
    for i,geo in enumerate(rebuilt.mesh_geometries):
        for a,z in zip(unit.mesh_geometries[i].streams,geo.streams):
            assert z.vertex_data.startswith(a.vertex_data), (key,i,'front stream changed')
        if i in changed:
            direct,reverse=triangle_keys(geometries[i])
            known=set(direct)
            assert all(k in known for k in reverse), (key,i,'missing reverse side')
    for entry in manifest['artifacts']:
        assert (destination/entry['path']).exists()
        if entry['path']==key+'.unit':entry['size']=len(output)
        else:assert (destination/entry['path']).stat().st_size==entry['size']
    (destination/'build.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    meta=json.loads((destination/'compile_manifest.json').read_text(encoding='utf-8'))
    meta['geometry']['triangles']=sum(g['triangle_count'] for g in geometries)
    meta['geometry']['vertices']=sum(g['vertices'] for g in geometries)
    meta['notes'].append('Authored two-sided opaque Cloth surfaces retain their reverse winding, opposite normals and matching UV/skin influences; original front streams and serialized skeleton are unchanged by this surface patch.')
    (destination/'compile_manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    row.update(status='patched',unit_sha256=hashlib.sha256(output).hexdigest(),
               original_front_streams_identical=True,serialized_skeleton_and_material_suffix_identical=True,
               reverse_side_coverage=1.,triangles=meta['geometry']['triangles'])
    print('GARMENT_SIDES',key,row['added_triangles'],flush=True)
    gc.collect()
(args.output/'garment_side_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('GARMENT_SIDES_COMPLETE',len(report['assets']),sum(r['status']=='patched' for r in report['assets'].values()),flush=True)
