"""Restore same-character hand weights in the measured current authoring pose."""
import json
from pathlib import Path
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

def apply(b,mesh,arm,reference=None):
    tag=getattr(b,'COSTUME_PROFILE',getattr(b,'MODEL_PROFILE',''))
    root=Path(__file__).resolve().parent/'skins_20261023'
    if reference is None:
        reference=json.loads((root/tag/'conversion.json').read_text(encoding='utf8'))['base']
    metadata=json.loads((root/'references'/reference/'source.json').read_text(encoding='utf8'))
    ref=np.load(root/'references'/reference/'source.npz')
    labels=[str(n)for n in ref['group_names']]
    original_bones={r['name']:r for r in metadata['bones']}
    fields=np.zeros((len(ref['positions']),len(labels)),np.float32)
    for slot in range(4):np.add.at(fields,(np.arange(len(fields)),ref['indices'][:,slot]),ref['weights'][:,slot])
    # source.npz skin_vertices intentionally also includes wrist-weighted
    # clothing. Those cuffs are not anatomical bare-hand donors.
    skin=np.zeros(len(fields),bool)
    skin[np.unique(ref['triangles'][np.isin(ref['materials'],metadata['skin_materials'])])]=True
    material_skin={i for i,m in enumerate(mesh.data.materials)if m and m.get('costume_skin')}
    vertices={v for p in mesh.data.polygons if p.material_index in material_skin for v in p.vertices}
    positions=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices])
    names={g.index:g.name for g in mesh.vertex_groups}
    # Legacy Si outfits contain small real edit-bone changes. A single rigid
    # hand alignment does not describe them. Read the actual original rest
    # matrices and transport its surface using the original skin weights.
    with b.bpy.data.libraries.load(metadata['source'],link=False)as(data_from,data_to):
        assert metadata['armature']in data_from.objects,metadata['armature']
        data_to.objects=[metadata['armature']]
    reference_arm=data_to.objects[0]
    reference_world=Matrix(metadata['source_armature_matrix'])
    rest_maps={}
    rest_errors=[]
    for name in labels:
        if name not in reference_arm.data.bones or name not in arm.data.bones:continue
        original=reference_world@reference_arm.data.bones[name].matrix_local
        current=arm.matrix_world@arm.data.bones[name].matrix_local
        fitted=current@original.inverted()
        rest_maps[name]=np.array(fitted)
        point=reference_world@reference_arm.data.bones[name].head_local
        rest_errors.append((fitted@point-arm.matrix_world@arm.data.bones[name].head_local).length)
    def below(name,root_name):
        seen=set()
        while name and name not in seen:
            if name==root_name:return True
            seen.add(name);name=original_bones.get(name,{}).get('parent')
        return False
    rows=[]
    for side in ('L','R'):
        hand=np.array([below(n,'手首.'+side)for n in labels])
        mass=fields[:,hand].sum(1)
        all_triangles=ref['triangles']
        anatomical=(mass[all_triangles]>.2).all(1)
        triangles=all_triangles[skin[all_triangles].all(1)&anatomical]
        glove_fallback=len(triangles)<100
        if glove_fallback:triangles=all_triangles[anatomical]
        assert len(triangles)>100,('Missing original hand surface',tag,side)
        needed=np.unique(triangles);source_points=ref['positions'][needed]
        posed=np.zeros_like(source_points,dtype=float);covered=np.zeros(len(needed))
        for j,name in enumerate(labels):
            weight=fields[needed,j]
            if not np.any(weight>0):continue
            assert name in rest_maps,('Missing original deform matrix',tag,name)
            transform=rest_maps[name]
            posed+=weight[:,None]*(source_points@transform[:3,:3].T+transform[:3,3])
            covered+=weight
        assert np.max(np.abs(covered-1))<1e-5,('Uncovered original hand donor',tag,side)
        points=ref['positions'].astype(float).copy();points[needed]=posed
        if glove_fallback:
            wrist=np.array(arm.matrix_world@arm.data.bones['手首.'+side].head_local)
            knuckle=np.array(arm.matrix_world@arm.data.bones['中指１.'+side].head_local)
            axis=knuckle-wrist;axis/=np.linalg.norm(axis)
            triangles=triangles[((points[triangles].mean(1)-wrist)@axis)>=0]
            assert len(triangles)>100,('Missing original glove hand surface',tag,side)
        error=max(rest_errors)
        q=points[triangles]
        area=np.linalg.norm(np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]),axis=1)
        triangles=triangles[area>1e-14]
        tree=BVHTree.FromPolygons(points.tolist(),triangles.tolist(),all_triangles=True)
        lo=points[triangles].min((0,1))-.012;hi=points[triangles].max((0,1))+.012
        candidates=[i for i in vertices if np.all(positions[i]>=lo)and np.all(positions[i]<=hi)]
        distances=[];delta=[]
        for vi in candidates:
            v=mesh.data.vertices[vi]
            location,normal,index,distance=tree.find_nearest(Vector(positions[vi]))
            if index is None or distance>.012:continue
            ids=triangles[index];a,z,c=points[ids];edge=z-a;other=c-a;offset=np.array(location)-a
            gram=np.array([[edge@edge,edge@other],[edge@other,other@other]])
            if abs(np.linalg.det(gram))<1e-20:continue
            s,t=np.linalg.solve(gram,[offset@edge,offset@other])
            bary=np.maximum([1-s-t,s,t],0);bary/=bary.sum()
            recovered=bary@fields[ids];recovered/=recovered.sum()
            previous={names[g.group]:g.weight for g in v.groups if names[g.group]in arm.data.bones}
            delta.append(float(sum(abs(previous.get(n,0)-recovered[j])for j,n in enumerate(labels))))
            for g in list(v.groups):
                if names[g.group]in arm.data.bones:mesh.vertex_groups[g.group].remove([vi])
            for j in np.flatnonzero(recovered>1e-7):
                group=mesh.vertex_groups.get(labels[j])
                assert group is not None and labels[j]in arm.data.bones,('Missing original hand group',tag,labels[j])
                group.add([vi],float(recovered[j]),'REPLACE')
            distances.append(float(distance))
        assert distances,('No original surface restored',tag,side)
        rows.append(dict(side=side,source_triangles=len(triangles),vertices=len(distances),
            source_surface='original skin material'if not glove_fallback else 'original glove forward of measured wrist plane',
            landmark_max_error_mm=error*1000,source_surface_distance_mm=(1000*np.quantile(distances,[0,.5,.9,1])).tolist(),
            weight_l1_change_quantiles=np.quantile(delta,[0,.5,.9,1]).tolist()))
    report=dict(profile=tag,reference_character=reference,
        method='same-character original hand triangle weights, transported by actual original/current rest-bone matrices',
        source_auxiliary_bones_retained=True,positions_uvs_normals_unchanged=True,
        cross_character_transfer=False,source_animation_available=False,sides=rows,gameplay_verified=False)
    if getattr(b,'HAND_AUTHORING_OUTPUT',None):
        output=Path(b.HAND_AUTHORING_OUTPUT)/'original_hand_weights.json'
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    reference_data=reference_arm.data
    b.bpy.data.objects.remove(reference_arm,do_unlink=True)
    if reference_data.users==0:b.bpy.data.armatures.remove(reference_data)
    print('COSTUME_ORIGINAL_HAND_WEIGHTS',json.dumps(report),flush=True)
