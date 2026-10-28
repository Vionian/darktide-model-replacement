"""Local source-hand subdivision, with interpolated UVs and deform weights."""
import json,pathlib
import bmesh
import numpy as np

def prepare(b,mesh,arm):
    # Source hand topology, UV seams, normals and deform weights are already
    # authored for the character.  MMR is used by the surface fitter for
    # measured joint contact, while this optional topology pass stays off.
    report={'profile':getattr(b,'MODEL_PROFILE',None),
            'source_file_unchanged':True,
            'localized_to':'disabled; native source hand topology and weights retained',
            'subdivision_enabled':False,'coincident_skin_vertices_welded':0,
            'UV_and_skin_weights':'retained from source blend'}
    if not getattr(b,'ENABLE_SOURCE_HAND_TOPOLOGY_EDIT',False):
        if getattr(b,'HAND_AUTHORING_OUTPUT',None):
            (pathlib.Path(b.HAND_AUTHORING_OUTPUT)/'hand_detail.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('ENDFIELD_HAND_DETAIL_DISABLED',json.dumps(report))
        return
    profile=getattr(b,'MODEL_PROFILE',None)
    tagged=bool(getattr(b,'COSTUME_PROFILE',None))
    if profile not in ('endministrator_f','si_ink_mist','si_short_skirt','si_lolita') and not tagged:return
    costume=tagged or profile in ('si_ink_mist','si_short_skirt','si_lolita')
    dense=tagged or profile in ('si_ink_mist','si_lolita')
    # This source has only ~2.7k hand triangles, unlike the dense EFMI hands.
    # One local split gives its palm and knuckles enough geometry to round.
    if getattr(b,'COSTUME_PROFILE','')=='roshia_lolita':dense=False
    if mesh.get('endfield_hand_subdivided'):return
    mapping=b.source_bone_targets(arm)
    groups={g.index:g.name for g in mesh.vertex_groups}
    eligible=set()
    for v in mesh.data.vertices:
        total=sum(g.weight for g in v.groups if mapping.get(groups[g.group],'').startswith(('j_lefthand','j_righthand')))
        if total>.95:eligible.add(v.index)
    skin={i for i,m in enumerate(mesh.data.materials)if m and
          (m.get('ink_mist_component')==5 or m.get('costume_skin') if costume else m.name=='肌')}
    before=len(mesh.data.vertices)
    saved_normals=None
    if costume:
        # bmesh round-trips do not reliably preserve custom split normals.
        # Carry original loop normals in a generic CORNER attribute, so the
        # hand-only edit cannot change the dress, head or uncovered legs.
        old=np.empty(len(mesh.data.loops)*3,np.float32)
        mesh.data.corner_normals.foreach_get('vector',old)
        saved_normals=mesh.data.attributes.new('__ink_hand_source_normals','FLOAT_VECTOR','CORNER')
        saved_normals.data.foreach_set('vector',old)
    bm=bmesh.new();bm.from_mesh(mesh.data)
    bm.verts.ensure_lookup_table()
    seam_welds=0
    if costume:
        # EFMI stores split vertices at UV/normal seams. Weld coincident skin
        # vertices before subdivision; per-loop UVs remain separate. This
        # avoids smoothing each little seam island as a separate surface.
        candidates=[v for v in bm.verts if v.index in eligible
                    and v.link_faces and all(f.material_index in skin for f in v.link_faces)]
        count=len(bm.verts)
        bmesh.ops.remove_doubles(bm,verts=candidates,dist=1e-7)
        seam_welds=count-len(bm.verts)
        bm.verts.ensure_lookup_table();bm.verts.index_update()
        deform=bm.verts.layers.deform.active
        hand_ids={i for i,n in groups.items()if mapping.get(n,'').startswith(('j_lefthand','j_righthand'))}
        eligible={v.index for v in bm.verts if sum(w for g,w in v[deform].items()if g in hand_ids)>.95}
    edges=[e for e in bm.edges if all(v.index in eligible for v in e.verts)
           and all(f.material_index in skin for f in e.link_faces)]
    # Built-in curved-edge interpolation rounds the actual geometry; deform
    # and UV custom-data layers interpolate along every new edge/face.
    selected_faces={f for f in bm.faces if f.material_index in skin and all(v.index in eligible for v in f.verts)}
    hand_region={v for f in selected_faces for v in f.verts}
    # The EFMI hands already have 12k faces each. Adding more subdivisions
    # cannot repair split shading and would overflow the native slot budget.
    cut=({'geom_inner':[],'geom_split':[]} if dense else
         bmesh.ops.subdivide_edges(bm,edges=edges,cuts=1,use_grid_fill=True,smooth=0))
    hand_region.update(v for v in cut['geom_inner']+cut['geom_split'] if isinstance(v,bmesh.types.BMVert))
    hand_region={v for v in hand_region if v.is_valid}
    interior=[v for v in hand_region if all(f.material_index in skin for f in v.link_faces)
              and all(e.is_manifold and all(w in hand_region for w in e.verts) for e in v.link_edges)]
    # A conservative Taubin pair rounds faceted outlines without the spiky
    # spherical edge interpolation on the source's triangulated nail tips.
    factors=(.24,-.25) if costume else (.35,-.20)
    for _ in range(3 if costume else 4):
        bmesh.ops.smooth_vert(bm,verts=interior,factor=factors[0],use_axis_x=True,use_axis_y=True,use_axis_z=True)
        bmesh.ops.smooth_vert(bm,verts=interior,factor=factors[1],use_axis_x=True,use_axis_y=True,use_axis_z=True)
    bm.normal_update();bm.to_mesh(mesh.data);bm.free()
    mesh.data.update()
    # Subdivision renumbers vertices; recompute the hand mask after bmesh.
    eligible={v.index for v in mesh.data.vertices if sum(
        g.weight for g in v.groups if mapping.get(groups[g.group],'').startswith(
            ('j_lefthand','j_righthand')))>.95}
    normals=np.empty(len(mesh.data.loops)*3,np.float32)
    normal_source=(mesh.data.attributes['__ink_hand_source_normals'].data if saved_normals is not None
                   else mesh.data.corner_normals)
    normal_source.foreach_get('vector',normals)
    normals=normals.reshape(-1,3)
    vertex_normals=np.empty(len(mesh.data.vertices)*3,np.float32)
    mesh.data.vertices.foreach_get('normal',vertex_normals)
    vertex_normals=vertex_normals.reshape(-1,3)
    for p in mesh.data.polygons:
        if p.material_index in skin:
            p.use_smooth=True
            for li in p.loop_indices:
                vi=mesh.data.loops[li].vertex_index
                if not costume or vi in eligible:normals[li]=vertex_normals[vi]
    mesh.data.normals_split_custom_set(normals)
    if saved_normals is not None:mesh.data.attributes.remove(mesh.data.attributes['__ink_hand_source_normals'])
    mesh['endfield_hand_subdivided']=True
    report={'profile':b.MODEL_PROFILE,'before_vertices':before,'after_vertices':len(mesh.data.vertices),
            'localized_to':'source hand skin, wrist boundary and garment edges excluded',
            'source_file_unchanged':True,'coincident_skin_vertices_welded':seam_welds,
            'subdivision_enabled':not dense,
            'UV_and_skin_weights':'interpolated using Blender bmesh custom-data layers'}
    if getattr(b,'HAND_AUTHORING_OUTPUT',None):
        (pathlib.Path(b.HAND_AUTHORING_OUTPUT)/'hand_detail.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('ENDFIELD_HAND_DETAIL',json.dumps(report))

def smooth_fitted_hands(groups,targets):
    """Round fitting seams on the final surface; keep the wrist boundary fixed."""
    for group in groups:
        ids=group['vertices'][group['triangles']]
        if not len(ids):continue
        points=group['retargeted_positions'];ji,jw=group['joint_indices'],group['joint_weights']
        palettes=[p for p,n in targets.items()if n.startswith(('j_lefthand','j_righthand'))]
        hand=np.where(np.isin(ji,palettes),jw,0).sum(1)>.95
        active=np.unique(ids[hand[ids]])
        if not len(active):continue
        # UV splits share a geometric location; smooth them together.
        _,inverse=np.unique(np.round(points,6),axis=0,return_inverse=True)
        count=int(inverse.max())+1
        vertices=np.zeros((count,3),np.float64);multiplicity=np.bincount(inverse)
        np.add.at(vertices,inverse,points);vertices/=multiplicity[:,None]
        edges=np.unique(np.sort(np.concatenate((ids[:,[0,1]],ids[:,[1,2]],ids[:,[2,0]])),axis=1),axis=0)
        edges=np.unique(np.sort(inverse[edges],axis=1),axis=0);edges=edges[edges[:,0]!=edges[:,1]]
        movable=np.zeros(count,bool);movable[inverse[active]]=True
        boundary=edges[movable[edges].sum(1)==1].ravel();movable[boundary]=False
        src=np.r_[edges[:,0],edges[:,1]];dst=np.r_[edges[:,1],edges[:,0]]
        degree=np.bincount(src,minlength=count);movable&=degree>2
        original=vertices.copy()
        for _ in range(10):
            for factor in (.46,-.47):
                neighbor=np.zeros_like(vertices);np.add.at(neighbor,src,vertices[dst])
                delta=neighbor/np.maximum(degree[:,None],1)-vertices
                vertices[movable]+=factor*delta[movable]
        delta=vertices-original
        points+=delta[inverse]
        print('COSTUME_FITTED_HAND_SMOOTH',len(active),'max_mm',float(np.linalg.norm(delta,axis=1).max()*1000))


def final_normals(mesh,groups,targets):
    """Normals of the fitted surface, rather than independently fitted frames."""
    if not getattr(mesh, 'get', lambda *_: None)('recompute_fitted_hand_normals', False):
        # Preserve the source corner normals transported through MMR's affine
        # map. Rebuilding averaged normals here can erase source nail edges and
        # blend across UV/material seams in a way the source did not author.
        return
    for group in groups:
        if group['material_name']!='肌':continue
        tri=group['triangles'];ids=group['vertices'][tri]
        if not len(ids):continue
        p=group['retargeted_positions'];v=p[ids]
        areas=np.cross(v[:,1]-v[:,0],v[:,2]-v[:,0])
        if np.sum(areas*group['normals'][tri].mean(1))<0:areas*=-1
        smooth=np.zeros_like(p)
        for c in range(3):np.add.at(smooth,ids[:,c],areas)
        smooth_lengths=np.linalg.norm(smooth,axis=1,keepdims=True)
        valid_smooth=np.isfinite(smooth).all(axis=1)&(smooth_lengths[:,0]>1e-12)
        smooth/=np.maximum(smooth_lengths,1e-12)
        ji,jw=group['joint_indices'],group['joint_weights']
        hands=[palette for palette,name in targets.items()if name.startswith(('j_lefthand','j_righthand'))]
        hand=np.where(np.isin(ji,hands),jw,0).sum(1)>.95
        # Opposite source faces can cancel the area-weighted sum at a seam.
        # Preserve the valid transported corner normal there instead of
        # overwriting it with zero (which has no octahedral encoding).
        skipped=hand[ids]&~valid_smooth[ids]
        if np.any(skipped):
            print('ENDFIELD_HAND_NORMAL_PRESERVED',json.dumps({
                'material':group['material_name'],'corners':int(skipped.sum()),
                'vertices':np.unique(ids[skipped]).tolist(),
                'reason':'opposing-or-degenerate-face-normal-sum'}))
        affected=hand[ids]&valid_smooth[ids]
        current=group['normals'][tri].copy()
        current[affected]=smooth[ids][affected]
        group['normals'][tri]=current
