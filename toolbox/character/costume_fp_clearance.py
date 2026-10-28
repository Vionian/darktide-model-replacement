"""First-person-only garment visibility from source arm distances."""
import numpy as np

def apply(b,mesh,arm,groups,targets):
    profile=getattr(b,'COSTUME_PROFILE','')
    if not profile:return
    strict=(profile.startswith('endministrator_devil') or profile in (
        'endministrator_penguin','laiwanting_simple','aitela_hiro',
        'gilberta_swimsuit','chenqianyu_sport','roshia_lolita',
        'si_ink_wash','si_lolita','si_short_skirt'))
    p=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices])
    allowed=np.zeros(len(p),bool);skin_allowed=np.zeros(len(p),bool)
    for side in ('.L','.R'):
        bones=[arm.data.bones.get(n+side)for n in ('腕','ひじ','手首','中指１','中指３')]
        if not all(bones):continue
        pts=[np.array(arm.matrix_world@x.head_local)for x in bones]
        for segment,(a,z)in enumerate(zip(pts[:-1],pts[1:])):
            axis=z-a;length=np.linalg.norm(axis);axis/=length
            t=(p-a)@axis;radius=np.linalg.norm(p-a-t[:,None]*axis,axis=1)
            lo=length*.15 if segment==0 else -.012/b.SCALE
            hi=length+.025/b.SCALE
            skin_allowed|=(t>lo)&(t<hi)&(radius<(.065 if segment>=2 else .080)/b.SCALE)
            cap=(.080 if segment<2 else .060)/b.SCALE
            allowed|=(t>lo)&(t<hi)&(radius<cap)
    materials=np.array([t.material_index for t in mesh.data.loop_triangles])
    # Wide sleeves can pass the source tube test yet be pulled
    # away by their mixed torso/helper maps. Also check the exported native
    # rest surface; distant fragments must not enter the FP draw at all.
    target_allowed=None
    if strict:
        unit=b.load_target_unit()
        names=b.named_node_map(unit,b.BonesResourceDT(b.Cursor(str(b.TEMPLATE/'qianxia_bones.bones'))))
        q=groups[0]['retargeted_positions'];target_allowed=np.zeros(len(q),bool)
        for side in ('left','right'):
            labels=['j_'+side+s for s in ('arm','forearm','hand','handmiddle3')]
            pts=[np.array(unit.scene_graph.nodes[names[n]].world_transform.translation) for n in labels]
            for segment,(a,z) in enumerate(zip(pts[:-1],pts[1:])):
                axis=z-a;length=np.linalg.norm(axis);axis/=length
                t=(q-a)@axis;radial=np.linalg.norm(q-a-t[:,None]*axis,axis=1)
                radius=(.085,.075,.070)[segment]
                target_allowed|=(t>(.15*length if segment==0 else -.025))&(t<length+.035)&(radial<radius)
    for i,g in enumerate(groups):
        mat=mesh.data.materials[i]
        if not mat:continue
        before=len(g['triangles']);ids=g['vertices']
        if mat.get('costume_skin') or mat.name in ('肌','身体','Skin','Body'):
            keep=skin_allowed[ids[:len(materials)]].all(1)
            if strict:
                arm_palettes=[pal for pal,name in targets.items() if name.startswith(('j_left','j_right'))
                              and any(t in name for t in ('arm','hand')) and 'shoulder' not in name]
                mass=np.where(np.isin(g['joint_indices'],arm_palettes),g['joint_weights'],0).sum(1)
                keep&=(mass[ids[:len(materials)]].min(1)>=.50)
            g['triangles']=np.flatnonzero((materials==i)&keep)
        else:
            tri=g['triangles'];g['triangles']=tri[allowed[ids[tri]].all(1)]
            if target_allowed is not None:
                tri=g['triangles'];g['triangles']=tri[target_allowed[ids[tri]].all(1)]
        print('COSTUME_FP_CLEARANCE',profile,mat.name,before,len(g['triangles']))
