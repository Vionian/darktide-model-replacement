"""Offline finger skin transfer onto native pivots using finished reference hands.

MMR rest articulation alone cannot fix where the mesh bends: the source MMD
joint transition weights were authored for different segment proportions. Fit
the surface first, then sample native reference weight fields on that surface.
The established profiles adapt the ring; Ink Mist adapts all five digits after
an actual compiled-surface comparison. Preserve total digit/palm influence and
all wrist/equipment drivers. No guessed runtime curl gain or angle cap.
"""
import pathlib,json
import numpy as np

REFERENCES=('roshia_arms','daniya_blue_arms','qianxia_arms','aimisi_arms')

def fields(b,targets,digit='ring',reference_assets=REFERENCES,destination=None):
    cache=getattr(b,'_digit_reference_fields',{})
    key=(digit,tuple(reference_assets),json.dumps(destination,sort_keys=True) if destination else None)
    if key in cache:return cache[key]
    inverse={n:p for p,n in targets.items()}
    result={'left':[],'right':[]}
    for asset in reference_assets:
        folder=b.ROOT/'Custom'/asset
        u=b.unit_dt.UnitResourceDT(b.Cursor(str(folder/(asset+'.unit'))))
        names=b.named_node_map(u,b.BonesResourceDT(b.Cursor(str(next(folder.glob('*.bones'))))))
        for side in result:
            wanted=[f'j_{side}hand{digit}{k}'for k in (1,2,3)]
            source_pal=[u.skins[0].node_indices.index(names[n])for n in wanted]
            points=[];values=[]
            for mesh in u.meshes:
                geo=u.mesh_geometries[mesh.geometry_index-1];cs={c.component.name:c for c in geo.channels}
                def read(n,method):c=cs[n];return getattr(geo.streams[c.stream],method)(c)
                p=read('POSITION','get_positions');j=read('BLENDINDICES','get_blendindices');w=read('BLENDWEIGHTS','get_blendweights')
                v=np.column_stack([np.where(j==pal,w,0).sum(1)for pal in source_pal])
                total=v.sum(1);sel=total>.5
                points.extend(p[sel]);values.extend(v[sel]/total[sel,None])
            pts=np.asarray(points,float);val=np.asarray(values,float)
            if destination:
                offsets=np.asarray([np.asarray(destination[n])-np.asarray(
                    u.scene_graph.nodes[names[n]].world_transform.translation) for n in wanted])
                pts=pts+val@offsets
            pts,unique=np.unique(pts,axis=0,return_index=True);val=val[unique]
            result[side].append((pts,val,asset))
    cache[key]=result;b._digit_reference_fields=cache
    return result

def adapt_weights(b,mesh,targets,result,source):
    if '__finger_width_scale'not in source:return result
    indices,weights,arm,points,normals=result
    ink=getattr(b,'MODEL_PROFILE',None)in ('si_ink_mist','si_short_skirt','si_lolita')
    digits=('thumb','index','middle','ring','pinky') if ink else ('ring',)
    reference_assets=('daniya_blue_arms','qianxia_arms','aimisi_arms') if ink else REFERENCES
    rows=[]
    for side,digit in ((s,d)for s in ('left','right')for d in digits):
        destination=source.get('__source_digit_targets')
        reference=fields(b,targets,digit,reference_assets,destination)
        palettes=[p for p,n in targets.items()if n in [f'j_{side}hand{digit}{k}'for k in (1,2,3)]]
        palettes=sorted(palettes,key=lambda p:targets[p])
        assert len(palettes)==3
        old=np.column_stack([np.where(indices==p,weights,0).sum(1)for p in palettes])
        total=old.sum(1);selected=np.flatnonzero(total>.5)
        if not len(selected):continue
        # Sample each surface position once; expanded native triangles and
        # nail/UV seams must receive a coherent spatial weight field.
        sample_points,inverse=np.unique(points[selected],axis=0,return_inverse=True)
        estimates=[]
        for rp,rw,asset in reference[side]:
            sampled=[]
            for start in range(0,len(sample_points),128):
                q=sample_points[start:start+128]
                distance=((q[:,None,:]-rp[None,:,:])**2).sum(2)
                nearest=np.argpartition(distance,3,axis=1)[:,:4]
                dist=np.take_along_axis(distance,nearest,axis=1)
                k=1/np.maximum(dist,1e-10);k/=k.sum(1,keepdims=True)
                sampled.append((rw[nearest]*k[:,:,None]).sum(1))
            estimates.append(np.concatenate(sampled))
        # Median protects against one reference's glove seam or sparse topology.
        fitted=np.median(estimates,axis=0);fitted/=fitted.sum(1,keepdims=True);fitted=fitted[inverse]
        before=old[selected]/total[selected,None]
        for v,new in zip(selected,fitted):
            merged={int(p):float(w)for p,w in zip(indices[v],weights[v])if w>0 and int(p)not in palettes}
            for p,w in zip(palettes,new):merged[p]=float(w*total[v])
            active=sorted(merged.items(),key=lambda item:-item[1])[:4]
            indices[v]=0;weights[v]=0
            normalization=sum(w for _,w in active)
            for slot,(p,w)in enumerate(active):indices[v,slot]=p;weights[v,slot]=w/normalization
        delta=np.abs(fitted-before)
        rows.append({'side':side,'digit':digit,'vertices':len(selected),'max_weight_change':float(delta.max()),
                     'mean_weight_change':float(delta.mean()),'references':list(reference_assets),
                     'native_nodes_unchanged':not bool(destination),
                     'reference_field_rebased_to_source_digits':bool(destination),
                     'method':'fitted-surface-nearest-reference-digit-weight-field'})
    if getattr(b,'HAND_AUTHORING_OUTPUT',None):
        (pathlib.Path(b.HAND_AUTHORING_OUTPUT)/'ring_skin_adaptation.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print('ENDFIELD_RING_SKIN_ADAPTATION',json.dumps(rows))
    return indices,weights,arm,points,normals
