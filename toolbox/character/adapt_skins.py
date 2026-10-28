"""Source-aware outfit recovery; originals are read-only.

GPU-only effects are not executed. Restored geometry, INI draw provenance,
surface-transfer distances and measured palette mappings remain inspectable.
"""
from pathlib import Path
import sys,json,re,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from skins_sources import source,OUT,SOURCES

VARIANTS={k:1 for k in SOURCES}
VARIANTS.update(endministrator_devil=4)
def profile(key,variant=1):return key if variant==1 else key+'_v'+str(variant)
def load(key,variant):
    from skins_geometry import read
    if key=='si_ink_wash':
        from eff_skin_reader import read as eff_read
        return eff_read()
    overrides={}
    if key=='endministrator_devil':overrides.update(sweapkey15=variant-1,sweapkey16=3)
    if key=='roshia_lolita':overrides.update(swapkey30=int(variant in (2,4)),swapkey31=int(variant in (3,4)))
    if key=='mifu_commander':overrides[chr(92)+'aslot_235107'+chr(92)+'pass']=200
    return read(key,overrides)

def texture_paths(key,r,d):
    """Prefer explicit active bindings; source component labels fill inherited bindings."""
    tex=d['textures'];items=list(tex.items())
    def find(*terms):
        return next((v for k,v in items if any(t.lower()in (k+' '+Path(v).name).lower()for t in terms)),None)
    diffuse=find('rabbitfx'+chr(92)+'diffuse','_BaseMap','diffusemap','_D.png')
    normal=find('normalmap','_BumpMap','_NM.png')
    packed=find('lightmap','_MetallicGlossMap')
    if key=='mifu_commander'and 'Component0'in d['source']['section']:
        diffuse=str(r.path('Resource_body_DiffuseMap'));normal=str(r.path('Resource_body_NormalMap'));packed=str(r.path('Resource_body_LightMap'))
    if key=='roshia_lolita':
        diffuse=tex.get('ps-t13',tex.get('ps-t15'));normal=tex.get('ps-t14',tex.get('ps-t17'));packed=tex.get('ps-t12',tex.get('ps-t16'))
        if not diffuse:
            token=d['source']['section'].split('.')[1].split('_')[0]
            for res,row in r.resources.items():
                path=r.path(res)
                if path and path.name.startswith(token):
                    if 'DiffuseMap'in path.name:diffuse=str(path)
                    elif 'NormalMap'in path.name:normal=str(path)
                    elif 'LightMap'in path.name:packed=str(path)
    if key in ('endministrator_penguin','laiwanting_simple'):
        c=int(d['source']['section'].rsplit('Component',1)[1])
        explicit={'endministrator_penguin':{0:(2,1,3),3:(17,15,14),5:(19,18,None),9:(23,22,21)},
                  'laiwanting_simple':{0:(3,1,2),1:(9,7,10),3:(19,18,None),8:(24,25,23)}}
        ids=explicit[key].get(c)
        if ids:
            diffuse,normal,packed=[str(r.path('Resource_Texture'+str(i)))if i is not None else None for i in ids]
    return [diffuse,normal,packed]

def prepare(key,variant=1):
    from PIL import Image
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation
    spec=source(key);tag=profile(key,variant);dest=OUT/tag;dest.mkdir(exist_ok=True);(dest/'textures').mkdir(exist_ok=True)
    r,draws,dups=load(key,variant)
    ref=np.load(OUT/'references'/spec['base']/'source.npz');meta=json.loads((OUT/'references'/spec['base']/'source.json').read_text(encoding='utf8'))
    assert meta.get('weight_contract')=='bone-groups-only-top4-normalized-v2','Re-export source bone-only weights'
    names=ref['group_names'];p0=ref['positions'].copy();valid={b['name']for b in meta['bones']}
    bone_parents={row['name']:row['parent']for row in meta['bones']}
    def below(name,root):
        cur=str(name);seen=set()
        while cur and cur not in seen:
            if cur==root:return True
            seen.add(cur);cur=bone_parents.get(cur)
        return False
    w0=np.zeros((len(p0),len(names)),np.float32)
    for k in range(4):np.add.at(w0,(np.arange(len(p0)),ref['indices'][:,k]),ref['weights'][:,k])
    w0[:,[n not in valid for n in names]]=0;w0/=np.maximum(w0.sum(1,keepdims=True),1e-12)
    mat=np.zeros(len(p0),np.int32)
    for tri,m in zip(ref['triangles'],ref['materials']):mat[tri]=m
    source_tree=cKDTree(p0);hair_mats=[i for i,n in enumerate(meta['materials'])if n.startswith(('发','髪'))and '影'not in n]
    skin_mats=[i for i,n in enumerate(meta['materials'])if n in ('肌','身体','Skin','Body')]
    face_mats=[i for i,n in enumerate(meta['materials'])if n in ('面','目','目HL','目白','目影','睫眉','睫','眉','二重','口内','齿','表情','发影','面具影')]
    filtered=[];skipped=[]
    for d in draws:
        dist,near=source_tree.query(d['positions']);votes=np.bincount(mat[near],minlength=len(meta['materials']));primary=int(votes.argmax())
        if len(d['faces'])<=4:skipped.append((d['source']['section'],'source placeholder/effect quad'));continue
        is_face=float(np.mean(np.isin(mat[near],face_mats)))>.65 and np.median(dist)<.01
        if is_face:skipped.append((d['source']['section'],'preserve optimized original face'));continue
        paths=texture_paths(key,r,d)
        is_hair=primary in hair_mats and np.mean(np.isin(mat[near],hair_mats))>.45
        # Source INI and atlas identities, not a nearest-clothing majority.
        section=d['source']['section']
        if key=='aitela_hiro' and '7fa97135_32529' in section:is_hair=True
        if key=='endministrator_devil' and section=='TextureOverride_Hair':is_hair=True
        # Preserve the selected replacement hairstyles and their own atlas.
        # Cocoa Puff's active back_hair/new_hair draws use its white body atlas.
        if is_hair and key not in ('aitela_hiro','endministrator_devil','roshia_lolita','roshia_cocoa_puff'):
            skipped.append((d['source']['section'],'retain original hair surface'));continue
        if is_hair and not paths[0]:
            skipped.append((d['source']['section'],'no replacement hair texture'));continue
        if key=='mifu_commander'and 'Component1'in d['source']['section']:
            skipped.append((d['source']['section'],'retain original hair and tail'));continue
        if key=='si_ink_wash' and not paths[0]:
            # Original components, including both horns, keep their CMB maps.
            skipped.append((d['source']['section'],'retained original unchanged component'));continue
        if not paths[0]and key in ('gilberta_swimsuit','saixi_swimsuit','chenqianyu_sport'):
            component=re.search(r'Component(\d+)',d['source']['section']);c=int(component[1])
            if (key,c) in {('gilberta_swimsuit',1),('gilberta_swimsuit',8),('saixi_swimsuit',8),('saixi_swimsuit',12),('chenqianyu_sport',5)}:
                exemplar=next(x for x in draws if any('rabbitfx'+chr(92)+'diffuse'in t for t in x['textures']))
                paths=texture_paths(key,r,exemplar)
        d.update(paths=paths,primary_material=primary,is_hair=bool(is_hair),
                 skin=primary in skin_mats or bool(paths[0]and any(t in Path(paths[0]).name.lower()for t in ('body','arm_d'))))
        if key=='roshia_cocoa_puff':
            # This author's Body atlas is shared by skin, skirt, sleeves and
            # hair. Its filename cannot select skin donors or backface culling.
            # The inspected original material votes distinguish those draws.
            d['skin']=primary in skin_mats
        if ((key=='endministrator_penguin' and section.endswith('Component5'))
            or (key=='endministrator_devil' and section.endswith('Component1'))
            or (key=='endministrator_devil' and section.endswith('Component0') and d['source']['start'] in (0,128082))
            or (key=='aitela_hiro' and '0b2ddd81_16539' in section)):
            d['skin']=True
        filtered.append(d)
    # Fit each source hand onto the imported rest surface before transferring
    # digit fields. The later native/MMR fit uses this same source skeleton.
    hand=np.array([bool(re.search(r'手首|指',str(n)))and not any(t in n for t in ('dummy','shadow'))for n in names])
    arm=np.array([bool(re.search(r'腕|ひじ|肘|手首|指',str(n)))and not any(t in n for t in ('dummy','shadow','sleeve'))for n in names])
    points=p0.copy();poses={};fit_report=[]
    for side,sign in (('.L',1),('.R',-1)):
        mask=hand&np.array([str(n).endswith(side)for n in names]);ids=np.flatnonzero(w0[:,mask].sum(1)>.8)
        old=np.unique(p0[ids],axis=0)
        if not len(old):raise ValueError(('No authored source hand',key,side))
        candidates=[]
        for d in filtered:
            if d['is_hair']:continue
            p=d['positions'];region=(sign*p[:,0]>.32)&(p[:,2]>.65)&(p[:,2]<1.35)
            if region.sum()>80:candidates.append(p[region])
        if not candidates:raise ValueError(('No costume hand surface',key,side))
        best=None
        shoulder=np.asarray(next(b['head']for b in meta['bones']if b['name']=='腕'+side))
        for candidate in candidates:
            target=np.unique(candidate,axis=0)
            if len(target)<60:continue
            for angle in (0,13.5*sign,-13.5*sign):
                linear=Rotation.from_euler('y',angle,degrees=True).as_matrix();translation=shoulder-linear@shoulder;tree=cKDTree(target)
                for _ in range(40):
                    dist,near=tree.query(old@linear.T+translation);keep=dist<=np.quantile(dist,.85)
                    a,z=old[keep],target[near[keep]];ac=a-shoulder;zc=z-shoulder
                    u,s,vt=np.linalg.svd(ac.T@zc);rot=vt.T@u.T
                    if np.linalg.det(rot)<0:vt[-1]*=-1;rot=vt.T@u.T
                    linear=rot;translation=shoulder-linear@shoulder
                error=float(np.median(tree.query(old@linear.T+translation)[0]))
                if best is None or error<best[0]:best=(error,linear.copy(),translation.copy())
        error,linear,translation=best
        if error>.009:raise ValueError(('Source hand rest fit requires inspection',key,side,error))
        # Match Blender's actual edit-bone transform of the root and ALL its
        # descendants. Name matching omitted Bip001 FingerTop/Hand_ty helpers
        # and left their donor vertices in a different rest pose.
        descendants=np.array([below(n,'腕'+side)for n in names])
        factor=w0[:,descendants].sum(1)
        points=points*(1-factor[:,None])+(p0@linear.T+translation)*factor[:,None]
        transform=np.eye(4);transform[:3,:3]=linear;transform[:3,3]=translation;poses[side]=transform.tolist()
        fit_report.append(dict(side=side,median_distance=error,scale=float(np.cbrt(np.linalg.det(linear)))))
    from costume_anatomical_domains import nearest as nearest_anatomy,is_arm as anatomical_arm,TORSO
    posed_bones=[]
    for bone in meta['bones']:
        row=dict(bone)
        for side,transform in poses.items():
            if below(bone['name'],'腕'+side):
                m=np.array(transform)
                row['head']=(m@np.r_[bone['head'],1])[:3].tolist()
                row['tail']=(m@np.r_[bone['tail'],1])[:3].tolist()
        posed_bones.append(row)
    tree=cKDTree(points)
    source_hand_ids=ref['skin_vertices'][w0[ref['skin_vertices']][:,hand].sum(1)>.5]
    source_hand_tree=cKDTree(points[source_hand_ids])
    explicit_sides={}
    for raw_side in ('L','R'):
        samples=[];masses=[]
        for draw in filtered:
            for raw,path in enumerate(draw.get('bone_paths',[])):
                if path.rsplit('/',1)[-1]!='Bip001_'+raw_side+'_Hand':continue
                mass=np.where(draw['raw_indices']==raw,draw['raw_weights'],0).sum(1)
                if mass.sum()>.1:
                    samples.append(float(mass@draw['positions'][:,0]));masses.append(float(mass.sum()))
        if masses:
            center=sum(samples)/sum(masses)
            candidates={side:next(b['head'][0]for b in meta['bones']if b['name']=='手首.'+side)for side in ('L','R')}
            matching=[side for side,x in candidates.items()if x*center>0]
            assert len(matching)==1 and abs(center)>.1,('Ambiguous EFF side',key,raw_side,center)
            explicit_sides[raw_side]=matching[0]
    if explicit_sides:assert set(explicit_sides.values())=={'L','R'},explicit_sides
    # Palette numbers are measured separately per source buffer.
    palettes={};evidence=[];hand_palettes={}
    for palette in {d['source_palette']for d in filtered}:
        group=[d for d in filtered if d['source_palette']==palette]
        scores={};masses={}
        for d in group:
            p=d['positions'];dist,near=tree.query(p);eligible=dist<.018
            for raw in np.unique(d['raw_indices']):
                mass=np.where(d['raw_indices']==raw,d['raw_weights'],0).sum(1);m=mass*eligible
                if m.sum()<.01:continue
                scores[int(raw)]=scores.get(int(raw),0)+m@w0[near];masses[int(raw)]=masses.get(int(raw),0)+m.sum()
        measured={}
        for raw,score in scores.items():
            gi=int(np.argmax(score));agreement=float(score[gi]/masses[raw])
            if agreement>.92:
                measured[raw]=gi;evidence.append(dict(buffer=palette,raw=raw,bone=str(names[gi]),agreement=agreement))
        # A joint's source weights are blended around knuckles, so a mean
        # majority score cannot identify its palette reliably. Compare the
        # entire weight field; this separates touching neighbouring digits.
        from costume_hand_weights import palette_correspondence
        hand_map,hand_evidence=palette_correspondence(group,tree,points,w0,names)
        measured.update(hand_map);hand_palettes[palette]=set(hand_map.values())
        evidence.extend(dict(buffer=palette,**row)for row in hand_evidence)
        # EFF packages retain explicit bone paths. Their indices are local to
        # each mesh, so resolve those names instead of guessing a GPU palette.
        if 'bone_paths'in group[0]:
            finger_names=('親指','人指','中指','薬指','小指')
            for raw,path in enumerate(group[0]['bone_paths']):
                leaf=path.rsplit('/',1)[-1]
                match=re.fullmatch(r'Bip001_([LR])_Finger([0-4])([12]?)',leaf)
                candidate=None
                if match:
                    side,digit,segment=match.groups();side=explicit_sides[side];number=int(segment or 0)+(0 if digit=='0'else 1)
                    candidate=finger_names[int(digit)]+'０１２３'[number]+'.'+side
                else:
                    m=re.fullmatch(r'Bip001_([LR])_(Hand|Forearm|UpperArm|Clavicle|Thigh|Calf|Foot|Toe0)',leaf)
                    if m:
                        side,part=m.groups();side=explicit_sides[side];candidate={'Hand':'手首','Forearm':'ひじ','UpperArm':'腕','Clavicle':'肩','Thigh':'足','Calf':'ひざ','Foot':'足首','Toe0':'つま先'}[part]+'.'+side
                if candidate in names:
                    measured[raw]=int(np.flatnonzero(names==candidate)[0])
        palettes[palette]=measured
    hair_groups=np.array([bool(re.search(r'hair|ear_|髪|发|strand',str(n),re.I))for n in names])
    dynamic_groups=np.array([bool(re.search(r'hair|ear_|髪|发|strand|cloth|skirt|裙|cape|tail|ribbon|sleeve|dummy|shadow',str(n),re.I))for n in names])
    # The original clothed character may expose no elbow/upper-arm skin. A
    # skin-only tree then chooses a distant hand for a new bare arm. Use the
    # complete original body surface, collapsing garment controls through the
    # actual source bone hierarchy onto their anatomical parent.
    bone_parents={row['name']:row['parent']for row in meta['bones']}
    core=re.compile(r'^(肩|腕|ひじ|肘|手首|足|ひざ|足首|つま先|親指[０１２３]|人指[１２３]|中指[１２３]|薬指[１２３]|小指[１２３])\.[LR]$')
    core_names={str(n)for n in names if core.fullmatch(str(n)) or str(n)in ('腰','下半身','上半身','上半身1','上半身2','上半身3','首','頭')}
    index_by_name={str(n):i for i,n in enumerate(names)}
    anatomical=np.zeros_like(w0)
    for i,n in enumerate(names):
        cur=str(n);seen=set()
        while cur not in core_names and cur and cur not in seen:
            seen.add(cur);duplicate=re.sub(r'D(?=\.[LR]$)','',cur)
            cur=duplicate if duplicate!=cur and duplicate in core_names else bone_parents.get(cur)
        if cur in core_names:anatomical[:,index_by_name[cur]]+=w0[:,i]
    body_materials=skin_mats+[i for i,n in enumerate(meta['materials'])if str(n).startswith(('Cloth','服','衣'))]
    body_ids=np.unique(ref['triangles'][np.isin(ref['materials'],body_materials)])
    skin_ids=body_ids[anatomical[body_ids].sum(1)>.5]
    skin_field=anatomical[skin_ids];skin_field/=np.maximum(skin_field.sum(1,keepdims=True),1e-12)
    skin_tree=cKDTree(points[skin_ids])
    head_index=next(i for i,n in enumerate(names)if n=='頭')
    head_allowed=hair_groups.copy();head_allowed[head_index]=True
    head_ids=np.flatnonzero(w0[:,head_allowed].sum(1)>.5)
    head_field=w0[head_ids].copy();head_field[:,~head_allowed]=0
    head_field/=np.maximum(head_field.sum(1,keepdims=True),1e-12)
    head_tree=cKDTree(points[head_ids])
    arrays={'group_names':names};rows=[]
    for d in filtered:
        p,n,uv,faces=[d[k]for k in ('positions','normals','uv','faces')]
        arm_garment=((key=='roshia_cocoa_puff' and d['source']['section']=='CommandList_Draw_Component6' and d['source']['start']==534024)
            or (key=='endministrator_devil' and d['source']['section']=='CommandList_Draw_Component0' and d['source']['start']==752118))
        transfer_policy='nearest-source-surface'
        skin=d['skin'] and not d['is_hair'];field=skin_field if skin else w0;donor_tree=skin_tree if skin else tree
        if not skin and not d['is_hair'] and str(meta['materials'][d['primary_material']]).startswith(('Cloth','服','衣')):
            garment_ids=np.unique(ref['triangles'][ref['materials']==d['primary_material']])
            field=w0[garment_ids];donor_tree=cKDTree(points[garment_ids])
            transfer_policy='matched-original-garment-material-surface'
        head_hair=d['is_hair'] and key=='aitela_hiro'
        if head_hair:
            field=head_field;donor_tree=head_tree;transfer_policy='head-and-hair-only-source-donors'
        if arm_garment:
            # These inspected source draws are detached sleeve/cuff pieces,
            # not gloves. Their closest original cape/skirt or exposed finger
            # is not a valid donor. Use the same character's original arm
            # surface and preserve the whole original hand as a wrist anchor.
            # A source draw can contain both sleeves and waist fabric. Its
            # arm flag is only a candidate; bind each region by actual anatomy.
            garment_fallback_field=field
            field=anatomical.copy()
            garment_domain=nearest_anatomy(p,posed_bones)
            arm_region=np.array([anatomical_arm(str(n))for n in garment_domain])
            torso_columns=np.array([str(n)in TORSO for n in names])
            torso_field=anatomical.copy();torso_field[:,~torso_columns]=0
            torso_donors=np.flatnonzero(torso_field.sum(1)>.5)
            torso_field/=np.maximum(torso_field.sum(1,keepdims=True),1e-12)
            fallback_dist,fallback_near=cKDTree(points[torso_donors]).query(p,k=4)
            fallback_kernel=1/np.maximum(fallback_dist,1e-6)**2;fallback_kernel/=fallback_kernel.sum(1,keepdims=True)
            fallback_weights=np.einsum('nk,nkg->ng',fallback_kernel,torso_field[torso_donors[fallback_near]])
            for side in ('L','R'):
                digit=np.array([bool(re.fullmatch(r'(親指[０１２３]|人指[１２３]|中指[１２３]|薬指[１２３]|小指[１２３])\.'+side,str(x)))for x in names])
                field[:,index_by_name['手首.'+side]]+=field[:,digit].sum(1);field[:,digit]=0
            dist=np.empty((len(p),4),np.float32);near=np.empty((len(p),4),np.int64)
            for side,sign in (('L',1),('R',-1)):
                groups=np.array([str(x)in ('腕.'+side,'ひじ.'+side,'肘.'+side,'手首.'+side)for x in names])
                donors=body_ids[field[body_ids][:,groups].sum(1)>.9]
                use=np.flatnonzero(p[:,0]*sign>0)
                dd,nn=cKDTree(points[donors]).query(p[use],k=4)
                dist[use]=dd;near[use]=donors[nn]
            transfer_policy='inspected-detached-cuff: corresponding-original-character-arm-surface, fingers-collapsed-to-wrist'
        elif key=='laiwanting_simple' and d['skin'] and 'Component3' in d['source']['section']:
            # The simplified outfit's exposed thighs straddle the pelvis seam.
            # Query a wider neighbourhood, then keep same-side donors within a
            # local height band so one leg can never borrow the other leg's
            # knee/ankle field and form a long animated triangle.
            donor_points=points[skin_ids]
            # Query each leg's donor cloud independently.  A global nearest-
            # neighbour query can return only the opposite leg near a thin
            # inner-thigh seam; falling back to those vertices gives that
            # triangle the wrong animated leg weights and creates a long
            # stretched spike.  Keep the seam's vertical band when it exists,
            # but if the band is sparse, pad from the same-side cloud only.
            left_ids=np.flatnonzero(donor_points[:,0]<-.018)
            right_ids=np.flatnonzero(donor_points[:,0]>.018)
            center_ids=np.arange(len(donor_points))
            donor_sets={
                'left':(left_ids,cKDTree(donor_points[left_ids])) if len(left_ids) else None,
                'right':(right_ids,cKDTree(donor_points[right_ids])) if len(right_ids) else None,
                'center':(center_ids,donor_tree),
            }
            side_keys=np.where(p[:,0]<0,'left',np.where(p[:,0]>0,'right','center'))
            dist=np.empty((len(p),4),dtype=np.float32);near=np.empty((len(p),4),dtype=np.int64)
            for side in ('left','right','center'):
                side_rows=np.flatnonzero(side_keys==side)
                if not len(side_rows):continue
                donor_set=donor_sets[side]
                if donor_set is None:
                    raise ValueError(f'{key}: source body has no {side}-side thigh skin donors')
                donor_ids,side_tree=donor_set
                k=min(24,len(donor_ids))
                query_dist,query_local=side_tree.query(p[side_rows],k=k)
                if k==1:query_dist=query_dist[:,None];query_local=query_local[:,None]
                for local_row,row in enumerate(side_rows):
                    candidate_dist=query_dist[local_row]
                    candidate_ids=donor_ids[query_local[local_row]]
                    in_band=np.abs(donor_points[candidate_ids,2]-p[row,2])<=.20
                    # Preserve all in-band donors, including fewer than four.
                    # If that band is empty, nearest same-side donors are the
                    # only fallback; the opposite leg is never introduced.
                    selected=np.flatnonzero(in_band)
                    order=selected if len(selected) else np.arange(len(candidate_ids))
                    order=order[np.argsort(candidate_dist[order])]
                    if len(order)<4:order=np.pad(order,(0,4-len(order)),mode='edge')
                    order=order[:4]
                    near[row]=candidate_ids[order];dist[row]=candidate_dist[order]
            transfer_policy='thigh-side-and-height-constrained-skin-donors'
        else:
            dist,near=donor_tree.query(p,k=4)
        kernel=1/np.maximum(dist,1e-6)**2;kernel/=kernel.sum(1,keepdims=True)
        w=np.zeros((len(p),len(names)),np.float32)
        for start in range(0,len(p),512):w[start:start+512]=np.einsum('nk,nkg->ng',kernel[start:start+512],field[near[start:start+512]])
        if arm_garment:w[~arm_region]=fallback_weights[~arm_region]
        measured=palettes[d['source_palette']]
        hand_distance=source_hand_tree.query(p)[0]
        authored_hand=np.zeros(len(p),np.float32)
        # Preserve confirmed source authored palettes, especially adjacent digits.
        explicit='bone_paths'in d
        for vi,(ii,ww)in enumerate(zip(d['raw_indices'],d['raw_weights'])):
            known={}
            for ri,val in zip(ii,ww):
                gi=measured.get(int(ri))
                trusted_hand=gi in hand_palettes[d['source_palette']]
                constrained_thigh=(key=='laiwanting_simple' and 'Component3' in d['source']['section']
                                   and abs(p[vi,0])<.3 and p[vi,2]<.95)
                allowed=gi is not None and (not head_hair or head_allowed[gi]) and (not skin or not dynamic_groups[gi])
                if arm_garment:allowed=False
                if not explicit and gi is not None and hand[gi] and hand_distance[vi]>.018:
                    allowed=False
                # A palette label inferred from the hand region is evidence
                # only near the original source surface. The same raw channel
                # can otherwise bind a distant skirt/sleeve to a fingertip.
                # Explicit named EFF paths are not subject to this inference.
                if allowed and val>0 and not constrained_thigh and (explicit or dist[vi,0]<.004):
                    known[gi]=known.get(gi,0)+val
                    if trusted_hand:authored_hand[vi]+=val
            if known:
                w[vi]*=max(0,1-sum(known.values()))
                for gi,val in known.items():w[vi,gi]+=val
        if not d['is_hair']:
            w[:,hair_groups]=0
            core=(abs(p[:,0])<.22)&(p[:,2]>1.03)&(p[:,2]<1.42)
            w[np.ix_(core,hand)]=0
            # Preserve the original hand's digit identity at the source
            # surface. Broad merged palettes and sleeve samples are not hand
            # anatomy evidence. EFF's explicit named bones remain authoritative.
            if not explicit and not arm_garment:
                hand_mass=w0[:,hand].sum(1)
                hd,hn=tree.query(p)
                region=(hand_mass[hn]>.5)&(hd<.018)&(authored_hand<.5)
                if np.any(region):w[region]=w0[hn[region]]
        if key=='laiwanting_simple' and 'Component3' in d['source']['section']:
            # Even same-side donor vertices carry tiny opposite-leg seam weights.
            # Below the crotch those cannot be allowed onto either separate thigh.
            for side,sign in (('L',1),('R',-1)):
                region=(p[:,0]*sign>0)&(p[:,2]<.95)
                opposite=np.array([str(n).endswith('.'+('R'if side=='L'else'L')) and
                                   str(n).startswith(('足','ひざ')) for n in names])
                w[np.ix_(region,opposite)]=0
        if key=='endministrator_devil' and skin:
            # The clothed reference has no bare lower-body skin donors. Recover
            # leg anatomy from its complete surface, stripping all garment helpers.
            # Hands also lie below z=1 in the source A-pose. Height alone
            # reassigned their vertices to thighs and removed both FP hands.
            lower=(p[:,2]<1.00)&(abs(p[:,0])<.28)
            for side,sign in (('L',1),('R',-1)):
                allowed=np.array([str(n)=='下半身' or (str(n).endswith('.'+side) and
                                 str(n).startswith(('足','ひざ')))for n in names])
                field_leg=w0.copy();field_leg[:,~allowed]=0
                donors=np.flatnonzero((points[:,0]*sign>0)&(field_leg.sum(1)>.5))
                field_leg/=np.maximum(field_leg.sum(1,keepdims=True),1e-12)
                use=np.flatnonzero(lower&(p[:,0]*sign>0))
                if len(use):
                    dd,nn=cKDTree(points[donors]).query(p[use],k=4)
                    kk=1/np.maximum(dd,1e-6)**2;kk/=kk.sum(1,keepdims=True)
                    w[use]=np.einsum('nk,nkg->ng',kk,field_leg[donors[nn]])
            # The original clothed mesh also lacks bare abdomen donors.
            # A nearest *skin* query selected fingers for belly/hip vertices.
            # Recover the complete source torso field and keep torso groups.
            # A rectangular torso mask included bare elbows in the rotated
            # source pose. Classify by the same actual source skeleton instead.
            torso=np.isin(nearest_anatomy(p,posed_bones),list(TORSO))
            torso_groups=np.array([str(n) in ('腰','下半身','上半身','上半身1','上半身2','首')
                                   or str(n).startswith('胸') for n in names])
            field_torso=w0.copy();field_torso[:,~torso_groups]=0
            donors=np.flatnonzero((abs(points[:,0])<.25)&(field_torso.sum(1)>.5))
            field_torso/=np.maximum(field_torso.sum(1,keepdims=True),1e-12)
            use=np.flatnonzero(torso)
            if len(use):
                dd,nn=cKDTree(points[donors]).query(p[use],k=4)
                kk=1/np.maximum(dd,1e-6)**2;kk/=kk.sum(1,keepdims=True)
                w[use]=np.einsum('nk,nkg->ng',kk,field_torso[donors[nn]])
            transfer_policy+=';lower-body-anatomical-only-donors'
        if key=='endministrator_penguin' and d['source']['section'].endswith('Component3') and d['source']['start']==594:
            w[:]=0;w[:,next(i for i,n in enumerate(names)if n=='ひじ.R')]=1
            transfer_policy='source-watch-rigid-right-forearm-no-finger-influence'
        empty=w.sum(1)<1e-8
        fallback=next((i for i,n in enumerate(names)if n=='上半身2'),next(i for i,n in enumerate(names)if n=='上半身'))
        w[empty,fallback]=1
        ii=np.argpartition(w,-4,axis=1)[:,-4:];ww=np.take_along_axis(w,ii,axis=1);ww/=np.maximum(ww.sum(1,keepdims=True),1e-12)
        paths=[]
        for role,path in zip(('D','N','P'),d['paths']):
            if not path or path=='None':paths.append(None);continue
            path=Path(path);assert path.is_file(),path
            target=dest/'textures'/(hashlib.sha256(str(path).encode()).hexdigest()[:12]+'_'+role+'.png')
            if not target.exists():
                im=Image.open(path).convert('RGBA')
                if max(im.size)>4096:im.thumbnail((4096,4096),Image.Resampling.LANCZOS)
                im.save(target)
            paths.append(str(target))
        # Source alpha cutouts remain geometry on the proven opaque path.
        cutout=None
        if paths[0]:
            alpha=np.asarray(Image.open(paths[0]))[:,:,3]/255.
            if np.quantile(alpha,.05)<.5:
                from si_ink_mist_cutouts import trim
                p,n,uv,faces,ii,ww,cutout=trim(p,n,uv,faces,ii,ww,alpha,.35,max_depth=2 if d['is_hair'] else 1)
        if not len(faces):continue
        if key=='endministrator_devil' and skin and 'Component0' in d['source']['section']:
            # The closed skirt covers this upper-thigh band in all four styles.
            # Remove only hidden source skin, leaving its exposed hem unchanged.
            covered=(p[:,2]>.83)&(p[:,2]<1.02)&(abs(p[:,0])<.175)&(abs(p[:,1])<.14)
            faces=faces[~covered[faces].all(1)]
        row=dict(section=d['source']['section'],start=d['source']['start'],name='Costume_'+tag+'_'+str(len(rows)),
                 vertices=len(p),triangles=len(faces),texture_paths=paths,skin=skin,is_hair=d['is_hair'],
                 two_sided=not skin,primary_material=d['primary_material'],cutout=cutout,
                 arm_garment=arm_garment,
                 source_transfer_distance=np.quantile(dist[:,0],[.5,.9,.99,1]).tolist(),
                 transfer_policy=transfer_policy)
        i=len(rows);rows.append(row)
        for field,value in dict(positions=p,normals=n,uv=uv,faces=faces,indices=ii,weights=ww).items():arrays[str(i)+'_'+field]=value
    np.savez_compressed(dest/'restored_meshes.npz',**arrays)
    report=dict(key=key,variant=variant,profile=tag,base=spec['base'],source=str(spec['folder']),source_ini=str(spec['ini']),
                source_arm_pose_maps=poses,hand_fits=fit_report,palette_correspondence=evidence,
                explicit_source_side_map=explicit_sides,source_weight_contract=meta['weight_contract'],draws=rows,skipped=skipped,duplicates=dups,
                original_model_author='茶叶味香皂',source_animation_available=False,
                limitations=['No original game animations supplied; outfit skin transfer is measured against original source surfaces.',
                             'Native PBR/geometric alpha cutouts approximate source-game shaders.'])
    (dest/'conversion.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('OUTFIT_RECOVERED',tag,len(rows),sum(x['triangles']for x in rows),fit_report,flush=True)

def blend(tag):
    import bpy,bmesh
    from mathutils import Matrix
    from mathutils.kdtree import KDTree
    dest=OUT/tag;report=json.loads((dest/'conversion.json').read_text(encoding='utf8'));data=np.load(dest/'restored_meshes.npz')
    meta=json.loads((OUT/'references'/report['base']/'source.json').read_text(encoding='utf8'))
    bpy.ops.wm.open_mainfile(filepath=meta['source'])
    for im in bpy.data.images:
        if im.filepath:im.filepath=bpy.path.abspath(im.filepath)
    def visible(c):
        c.exclude=False;c.hide_viewport=False;c.collection.hide_viewport=False
        for child in c.children:visible(child)
    visible(bpy.context.view_layer.layer_collection)
    original=bpy.data.objects[meta['mesh']];arm=bpy.data.objects[meta['armature']]
    original.data=original.data.copy()
    original.hide_viewport=False;original.hide_set(False);original.shape_key_clear()
    # Keep CMB face, original accessories omitted from the source replacement,
    # and original hair only if the outfit did not replace its silhouette.
    # Lolita's hair-component draw replaces the headband only; its INI explicitly
    # leaves the original game hair/ears active. It is not a replacement hairstyle.
    hair_replaced=report['key']!='roshia_lolita' and any(x['is_hair']for x in report['draws'])
    names={g.index:g.name for g in original.vertex_groups};headgroups={i for i,n in names.items()if n in ('頭','首')}
    tailgroups={i for i,n in names.items()if 'tail'in n.lower()}
    headmass=np.array([sum(g.weight for g in v.groups if g.group in headgroups)for v in original.data.vertices])
    tailmass=np.array([sum(g.weight for g in v.groups if g.group in tailgroups)for v in original.data.vertices])
    imported=np.concatenate([data[str(i)+'_positions']for i in range(len(report['draws']))]);tree=KDTree(len(imported))
    for i,p in enumerate(imported):tree.insert(p,i)
    tree.balance()
    origpos=np.array([list(original.matrix_world@v.co)for v in original.data.vertices]);dist=np.array([tree.find(p)[2]for p in origpos])
    head_z=next(b['head'][2]for b in meta['bones']if b['name']=='首')
    keep=[]
    for p in original.data.polygons:
        name=original.data.materials[p.material_index].name;ids=list(p.vertices)
        face=name in ('面','目','目HL','目白','睫眉','睫','眉','二重','口内','齿')
        hair=name.startswith(('发','髪'))and '影'not in name and not hair_replaced
        accessory=(headmass[ids]>.8).all()and origpos[ids,2].min()>head_z+.015 and dist[ids].min()>.003
        if hair_replaced and name.startswith(('发','髪')):accessory=False
        # Roshia's original red hood has head-weighted panels. Those are old
        # clothing, not horns/ears, and do not belong under replacement headwear.
        if report['base']=='roshia'and name.startswith('Cloth'):accessory=False
        tail=(tailmass[ids]>.6).all()and dist[ids].min()>.003
        if report['key']=='roshia_lolita' and (tailmass[ids]>.2).any():
            hair=False;tail=False
        if face or hair or accessory or tail:keep.append(p.index)
    bm=bmesh.new();bm.from_mesh(original.data);bm.faces.ensure_lookup_table();keepers=set(keep)
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.index not in keepers],context='FACES');bm.to_mesh(original.data);bm.free();original.data.update()
    for obj in bpy.context.scene.objects:obj.hide_render=True
    original.hide_render=False
    for side,transform in report['source_arm_pose_maps'].items():
        bpy.context.view_layer.objects.active=arm;arm.hide_set(False);arm.hide_viewport=False;bpy.ops.object.mode_set(mode='EDIT')
        root=arm.data.edit_bones['腕'+side]
        for bone in [root,*root.children_recursive]:bone.transform(Matrix(transform),scale=True,roll=True)
        bpy.ops.object.mode_set(mode='OBJECT')
    parts=[]
    for i,row in enumerate(report['draws']):
        prefix=str(i)+'_';me=bpy.data.meshes.new(row['name']);me.from_pydata(data[prefix+'positions'],[],data[prefix+'faces']);me.update()
        obj=bpy.data.objects.new(row['name'],me);bpy.context.collection.objects.link(obj)
        layer=me.uv_layers.new(name='UVMap');layer.data.foreach_set('uv',data[prefix+'uv'][np.array([l.vertex_index for l in me.loops])].ravel())
        for p in me.polygons:p.use_smooth=True
        me.normals_split_custom_set_from_vertices(data[prefix+'normals'])
        mat=bpy.data.materials.new(row['name']);mat.use_nodes=True
        for k in ('skin','two_sided','is_hair'):mat['costume_'+k]=row[k]
        mat['costume_arm_garment']=bool(row.get('arm_garment'))
        if row.get('transfer_policy')=='source-watch-rigid-right-forearm-no-finger-influence':mat['costume_rigid_wrist']='right'
        mat['costume_profile']=tag
        for role,path in zip(('diffuse','normal','packed'),row['texture_paths']):mat['costume_'+role]=path or ''
        nodes=mat.node_tree.nodes;links=mat.node_tree.links;bs=nodes.new('ShaderNodeBsdfPrincipled');output=nodes.new('ShaderNodeOutputMaterial');links.new(bs.outputs['BSDF'],output.inputs['Surface'])
        bs.inputs['Roughness'].default_value=.65 if row['skin']else .8
        if row['texture_paths'][0]:
            node=nodes.new('ShaderNodeTexImage');node.name='mmd_base_tex';node.image=bpy.data.images.load(row['texture_paths'][0],check_existing=True);node.image.alpha_mode='CHANNEL_PACKED';links.new(node.outputs['Color'],bs.inputs['Base Color'])
        else:
            # Unmodified original components need their actual original diffuse.
            donor=original.data.materials[row['primary_material']]
            if donor.node_tree:
                old=donor.node_tree.nodes.get('mmd_base_tex')
                if old and old.image:
                    node=nodes.new('ShaderNodeTexImage');node.name='mmd_base_tex';node.image=old.image;links.new(node.outputs['Color'],bs.inputs['Base Color'])
        me.materials.append(mat)
        for n in data['group_names']:obj.vertex_groups.new(name=str(n))
        for vi,(ii,ww)in enumerate(zip(data[prefix+'indices'],data[prefix+'weights'])):
            for gi,w in zip(ii,ww):
                if w>1e-5:obj.vertex_groups[int(gi)].add([vi],float(w),'REPLACE')
        obj.modifiers.new('Original source skeleton','ARMATURE').object=arm;parts.append(obj)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts+[original]:obj.select_set(True)
    bpy.context.view_layer.objects.active=original;bpy.ops.object.join()
    # Broad draw palettes can mix cuff/sleeve bones into source thumb/web
    # vertices. Those bones use a different native surface map and create
    # centimetre-long spikes even at rest. Keep anatomical hand ratios.
    from costume_hand_weights import clean as clean_hand_weights
    report['hand_weight_cleanup']=clean_hand_weights(original,arm)
    if report['key']=='si_ink_wash':
        from costume_hand_weights import clean_distal_residuals
        report['distal_weight_cleanup']=clean_distal_residuals(original,arm)
        from costume_hand_weights import reconcile_micro_edges
        report['micro_edge_weight_cleanup']=reconcile_micro_edges(original,meta['scale'])
    (dest/'conversion.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    canonical={};remap={}
    for i,mat in enumerate(original.data.materials):
        if 'costume_profile'not in mat:continue
        signature=tuple(mat.get(k)for k in ('costume_diffuse','costume_normal','costume_packed','costume_skin','costume_is_hair','costume_two_sided','costume_arm_garment'))
        remap[i]=canonical.setdefault(signature,i)
    for p in original.data.polygons:p.material_index=remap.get(p.material_index,p.material_index)
    # Original slot indices encode the character's face/eye and opaque accessory
    # policies. Leave empty original slots in place instead of renumbering them.
    for obj in list(bpy.data.objects):
        if obj!=original and obj.type=='MESH'and not obj.name.startswith(meta['mesh']+'__'):bpy.data.objects.remove(obj,do_unlink=True)
    # The native collector has finite uint16 slots. Dense garment-only collapse
    # is conservative and never changes source skin, fingers or face topology.
    counts={i:0 for i in range(len(original.data.materials))}
    for p in original.data.polygons:counts[p.material_index]+=len(p.vertices)-2
    slots=sum(int(np.ceil(c/(10922 if original.data.materials[i].get('costume_two_sided')else 21845)))for i,c in counts.items())
    if slots>29:
        ratio=max(.5,min(.95,26/slots))
        group=original.vertex_groups.new(name='__dense_outfit_only')
        ids={v for p in original.data.polygons if original.data.materials[p.material_index].get('costume_profile')and not original.data.materials[p.material_index].get('costume_skin')for v in p.vertices}
        group.add(list(ids),1,'REPLACE');mod=original.modifiers.new('Native garment slot budget','DECIMATE');mod.ratio=ratio;mod.vertex_group=group.name
        bpy.context.view_layer.objects.active=original;bpy.ops.object.modifier_apply(modifier=mod.name)
        report['garment_only_decimation']=dict(initial_slots=slots,ratio=ratio)
        (dest/'conversion.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    bpy.ops.wm.save_as_mainfile(filepath=str(dest/(tag+'.blend')))
    print('OUTFIT_BLEND',tag,len(original.data.vertices),len(original.data.polygons),flush=True)

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]if '--'in sys.argv else sys.argv[1:]
    if '--blend'in args:blend(args[0])
    else:
        for key in args or SOURCES:
            for variant in range(1,VARIANTS[key]+1):prepare(key,variant)
