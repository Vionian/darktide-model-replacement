"""Remove garment palette leakage from source hands, without changing anatomy."""
import re
import numpy as np


def palette_correspondence(draws, tree, donor_positions, donor_weights, names):
    """Identify authored hand channels by their entire spatial weight field."""
    anatomical = re.compile(r'^(手首|親指[０１２３0123]|人指[１２３123]|中指[１２３123]|薬指[１２３123]|小指[１２３123])\.[LR]$')
    columns = np.array([i for i, n in enumerate(names) if anatomical.fullmatch(str(n))])
    positions = np.concatenate([d['positions'] for d in draws])
    indices = np.concatenate([d['raw_indices'] for d in draws])
    weights = np.concatenate([d['raw_weights'] for d in draws])
    distance, nearest = tree.query(positions)
    fields = donor_weights[nearest][:, columns]
    eligible = (distance < .012) & (fields.sum(1) > .6)
    fields = fields*eligible[:, None]
    field_norms = np.linalg.norm(fields, axis=0)
    donor_mass = donor_weights[:, columns].sum(0)
    centers = donor_weights[:, columns].T@donor_positions/np.maximum(donor_mass[:, None], 1e-12)
    candidates = []
    for raw in np.unique(indices[eligible]):
        mass = np.where(indices == raw, weights, 0).sum(1)*eligible
        if mass.sum() < 1:
            continue
        score = mass@fields/np.maximum(np.linalg.norm(mass)*field_norms, 1e-12)
        ranking = np.argsort(score)[::-1]; best = ranking[0]
        gap = float(score[best]-score[ranking[1]])
        center = mass@positions/mass.sum()
        delta = float(np.linalg.norm(center-centers[best]))
        if score[best] >= .70 and gap >= .25 and delta < .018:
            candidates.append(dict(raw=int(raw), group=int(columns[best]),
                                   bone=str(names[columns[best]]), correlation=float(score[best]),
                                   next_candidate_margin=gap, centroid_distance=delta,
                                   method='whole-hand-weight-field-cosine-and-centroid'))
    # Competing raw channels are not proof of two distinct source joints.
    # Accept the strongest unique field; retain measured fallback elsewhere.
    result={}; evidence=[]; used=set()
    for row in sorted(candidates,key=lambda r:-r['correlation']):
        if row['group'] in used:
            continue
        used.add(row['group']); result[row['raw']]=row['group']; evidence.append(row)
    return result,evidence


def clean(mesh, armature):
    names = {g.index: g.name for g in mesh.vertex_groups}
    exact = re.compile(r'^(手首|親指[０１２３0123]|人指[１２３123]|中指[１２３123]|薬指[１２３123]|小指[１２３123])\.([LR])$')
    support = re.compile(r'^(手捩[^.]*|ひじ|肘)\.([LR])$')
    canonical = {i: exact.fullmatch(n) for i, n in names.items()}
    allowed = {s: {i for i, n in names.items() if
                      (canonical[i] and canonical[i][2] == s) or
                      (support.fullmatch(n) and support.fullmatch(n)[2] == s)}
               for s in ('L', 'R')}
    changed = []; max_removed = 0.; removed_groups = {}
    for v in mesh.data.vertices:
        weights = {g.group: g.weight for g in v.groups if g.weight > 1e-8}
        mass = {s: sum(w for i, w in weights.items()
                       if canonical[i] and canonical[i][2] == s) for s in ('L', 'R')}
        side = max(mass, key=mass.get)
        if mass[side] <= .5:
            continue
        total = sum(weights.values())
        keep = {i: w for i, w in weights.items() if i in allowed[side]}
        clean_total = sum(keep.values())
        removed = total-clean_total
        if removed <= 1e-6:
            continue
        assert clean_total > .5, ('Ambiguous source hand weights', v.index, mass)
        for i, w in weights.items():
            if i not in keep:
                mesh.vertex_groups[i].remove([v.index])
                removed_groups[names[i]] = removed_groups.get(names[i], 0)+1
        for i, w in keep.items():
            mesh.vertex_groups[i].add([v.index], float(w/clean_total), 'REPLACE')
        changed.append(v.index); max_removed = max(max_removed, removed/total)
    return {'contract': 'source-hand-anatomical-groups-only-v1',
            'changed_vertices': len(changed), 'max_removed_fraction': max_removed,
            'removed_groups': removed_groups, 'source_positions_changed': False,
            'source_digit_weights_renormalized_together': True}


def clean_distal_residuals(mesh, armature):
    """EFF fallback wrist weights must not reach beyond a finger knuckle."""
    names={g.index:g.name for g in mesh.vertex_groups};chains={}
    for side in ('L','R'):
        for digit,segments in (('親指','０１２'),('人指','１２３'),('中指','１２３'),
                               ('薬指','１２３'),('小指','１２３')):
            labels=[digit+k+'.'+side for k in segments]
            bones=[armature.data.bones.get(n)for n in labels]
            if not all(bones):continue
            origin=np.array(armature.matrix_world@bones[0].head_local)
            direction=np.array(armature.matrix_world@bones[1].head_local)-origin
            groups={i for i,n in names.items()if n in labels}
            chains[(side,digit)]=(groups,origin,direction)
    changed=0;removed_max=0.
    for v in mesh.data.vertices:
        weights={g.group:g.weight for g in v.groups if g.weight>1e-8}
        if not weights:continue
        masses={key:sum(weights.get(i,0)for i in row[0])for key,row in chains.items()}
        key=max(masses,key=masses.get);mass=masses[key]
        if mass<.75:continue
        groups,origin,direction=chains[key]
        p=np.array(mesh.matrix_world@v.co)
        axial=float((p-origin)@direction/max(direction@direction,1e-12))
        if axial<.5 or sum(w for k,w in masses.items()if k!=key)>.05:continue
        removed=sum(w for i,w in weights.items()if i not in groups)
        if removed<1e-6:continue
        for i in weights:
            if i not in groups:mesh.vertex_groups[i].remove([v.index])
        for i in groups:
            if i in weights:mesh.vertex_groups[i].add([v.index],float(weights[i]/mass),'REPLACE')
        changed+=1;removed_max=max(removed_max,removed)
    return dict(changed_vertices=changed,max_removed_mass=removed_max,
                scope='source-digit-majority distal surface only; original positions unchanged')


def reconcile_micro_edges(mesh, scale):
    """Reconcile tiny EFF cutout edges with discontinuous same-digit weights."""
    labels={g.index:g.name for g in mesh.vertex_groups}
    digit=re.compile(r'^(親指|人指|中指|薬指|小指)[０１２３0123]\.([LR])$')
    identities={i:(m[1],m[2])for i,n in labels.items()if(m:=digit.fullmatch(n))}
    fields=[];major=[]
    for v in mesh.data.vertices:
        row={g.group:g.weight for g in v.groups if g.weight>1e-8};mass={}
        for i,w in row.items():
            if i in identities:mass[identities[i]]=mass.get(identities[i],0)+w
        best=max(mass,key=mass.get)if mass else None
        major.append(best if best and mass[best]>.75 else None);fields.append(row)
    mesh.data.calc_loop_triangles()
    triangles=np.array([t.vertices[:]for t in mesh.data.loop_triangles])
    edges=np.unique(np.sort(np.concatenate([triangles[:,[0,1]],triangles[:,[1,2]],triangles[:,[2,0]]]),axis=1),axis=0)
    p=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices])*scale
    lengths=np.linalg.norm(p[edges[:,0]]-p[edges[:,1]],axis=1)
    parent={}
    def root(i):
        parent.setdefault(i,i)
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for a,z in edges[lengths<.0006]:
        a,z=int(a),int(z)
        if major[a] is None or major[a]!=major[z]:continue
        delta=max(abs(fields[a].get(i,0)-fields[z].get(i,0))for i in fields[a].keys()|fields[z].keys())
        if delta>.08:parent[root(z)]=root(a)
    groups={}
    for i in list(parent):groups.setdefault(root(i),[]).append(i)
    changed=0
    for ids in groups.values():
        if len(ids)<2:continue
        keys=set().union(*(fields[i]for i in ids))
        mean={k:sum(fields[i].get(k,0)for i in ids)/len(ids)for k in keys}
        for k,w in mean.items():mesh.vertex_groups[k].add(ids,float(w),'REPLACE')
        changed+=len(ids)
    return dict(changed_vertices=changed,components=sum(len(v)>1 for v in groups.values()),
                source_positions_changed=False,scope='sub-0.6mm same-digit discontinuous source edges only')
