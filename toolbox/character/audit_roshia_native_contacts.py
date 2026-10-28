"""Compare the actual compiled arm/hand rest rig with all three references."""
from pathlib import Path
import sys,json
import numpy as np
sys.path.insert(0,str(Path(__file__).parent))
import build_roshia_native as b

out=Path(sys.argv[sys.argv.index('--')+1]).resolve()
result={};reference=None
for asset,folder in [('qianxia',b.ROOT/'Custom/qianxia'),('daniya_blue',b.ROOT/'Custom/daniya_blue'),
                     ('aimisi',b.ROOT/'Custom/aimisi'),('roshia',out/'Custom/roshia'),('roshia_arms',out/'Custom/roshia_arms')]:
    b.TEMPLATE=folder
    unit=b.unit_dt.UnitResourceDT(b.Cursor(str(folder/(asset+'.unit'))))
    names=b.named_node_map(unit,b.BonesResourceDT(b.Cursor(str(folder/(asset+'_bones.bones')))))
    worlds={name:np.asarray(unit.scene_graph.nodes[i].world_transform)for name,i in names.items()
            if name.startswith(('j_left','j_right')) and any(k in name for k in ('shoulder','arm','hand'))}
    if reference is None:reference=worlds
    shared=sorted(set(worlds)&set(reference))
    error=max(float(abs(worlds[n]-reference[n]).max())for n in shared)
    result[asset]={'shared_upper_limb_nodes':len(shared),'maximum_rest_matrix_difference':error}
    assert error<1e-5,(asset,error)
    if asset.startswith('roshia'):
        if asset=='roshia':
            config=json.loads((out/'Custom/roshia_proportion_bones.json').read_text())
            supports=config['body'].get('shoulder_supports',[])
            roots=[]
            for support in supports:
                index=names[support['name']]
                node=unit.scene_graph.nodes[index]
                assert node.parent_index==names[support['parent']]
                assert not any(n.parent_index==index and name.startswith('j_') for name,i in names.items() for n in [unit.scene_graph.nodes[i]])
                assert index in unit.skins[0].node_indices
                roots.append(np.asarray(node.world_transform.translation))
            assert len(roots)==2
            result[asset]['shoulder_mesh_supports']={'count':len(roots),'root_spacing':float(np.linalg.norm(roots[0]-roots[1])),
                'native_driver_spacing':float(np.linalg.norm(reference['j_leftarm'][:3,3]-reference['j_rightarm'][:3,3])),
                'native_children':0}
        slots={slot.ID:mat.ID for slot,mat in unit.materials}
        core=[]
        for geo in unit.mesh_geometries:
            if slots[geo.materials[0].ID]!=b.hash64('content/mods/roshia/roshia_material_15'):continue
            p=np.frombuffer(geo.streams[1].vertex_data,'<f2').reshape(-1,4)[:,:3]
            ids=geo.index_stream.get_indices().reshape(-1,3)
            for tri in p[ids]:core.append(tri)
        if asset=='roshia':
            triangles=np.array(core);keys={};edges={}
            for tri in triangles:
                ids=[]
                for point in tri:
                    key=tuple(float(v)for v in point);ids.append(keys.setdefault(key,len(keys)))
                for a,c in zip(ids,ids[1:]+ids[:1]):
                    key=tuple(sorted((a,c)));edges[key]=edges.get(key,0)+1
            assert core and all(count==2 for count in edges.values())
            volume=float(np.sum(np.einsum('ij,ij->i',triangles[:,0].astype(float),
                np.cross(triangles[:,1].astype(float),triangles[:,2].astype(float))))/6)
            assert volume>1e-4
            result[asset]['tail_core']={'faces':len(core),'vertices':len(keys),'watertight':True,'signed_volume':volume}
    manifest=json.loads((folder/'build.json').read_text())
    if asset=='roshia':
        face_emission=sorted(a['resource']['name'] for a in manifest['artifacts']
            if a['role']=='primary' and a['resource']['type']=='texture'
            and a['resource']['name'].endswith('_em'))
        # The current face path deliberately uses diffuse-only rendering;
        # older candidates emitted this texture and needed a stale assertion.
        assert face_emission==[],face_emission
        result[asset]['facial_emission_resources']=face_emission
(out/'native_contact_audit.json').write_text(json.dumps(result,indent=2))
print('NATIVE_CONTACT_AUDIT',result)
