import pathlib,sys,json
import bpy,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from roshia_native_hand_surface import frame
from endfield_profiles import apply
key='endministrator_f';apply(b,key)
bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
u=b.load_target_unit();names=b.named_node_map(u,b.BonesResourceDT(b.Cursor(str(b.TEMPLATE/'qianxia_bones.bones'))))
m=bpy.data.objects[b.MESH_OBJECT_NAME];a=bpy.data.objects[b.ARMATURE_OBJECT_NAME]
mapping=b.source_bone_targets(a,names);gn={g.index:g.name for g in m.vertex_groups}
report={}
for side in ('left','right'):
    suffix='.R'if side=='right'else'.L';prefix=f'j_{side}handring'
    src=np.asarray([b.source_coordinate3()@(a.matrix_world@a.data.bones['薬指'+k+suffix].head_local)for k in ('１','２','３')])
    tar=np.asarray([u.scene_graph.nodes[names[prefix+str(k)]].world_transform.translation for k in (1,2,3)])
    report[side]={'source_joints':src.tolist(),'native_joints':tar.tolist(),'source':[],'refs':{}}
    axis=(src[2]-src[0]);axis/=np.linalg.norm(axis)
    for k in range(1,4):
        pts=[];ww=[]
        for v in m.data.vertices:
            w=sum(g.weight for g in v.groups if mapping.get(gn[g.group])==prefix+str(k))
            if w>.01:pts.append(list(b.source_coordinate3()@(m.matrix_world@v.co)));ww.append(w)
        pts=np.asarray(pts)
        report[side]['source'].append({'node':k,'quantiles_mm':(np.quantile((pts-src[0])@axis,[0,.1,.5,.9,1])*1000).tolist(),'weighted_mean_mm':float(np.average((pts-src[0])@axis,weights=ww)*1000)})
    for asset in ('daniya_blue_arms','qianxia_arms','aimisi_arms','roshia_arms'):
        folder=b.ROOT/'Custom'/asset;unit=b.unit_dt.UnitResourceDT(b.Cursor(str(folder/(asset+'.unit'))))
        ns=b.named_node_map(unit,b.BonesResourceDT(b.Cursor(str(next(folder.glob('*.bones'))))))
        rows=[]
        for k in range(1,4):
            points=[];weights=[]
            for mesh in unit.meshes:
                geo=unit.mesh_geometries[mesh.geometry_index-1];chs={c.component.name:c for c in geo.channels}
                def read(n,method):c=chs[n];return getattr(geo.streams[c.stream],method)(c)
                pp=read('POSITION','get_positions');jj=read('BLENDINDICES','get_blendindices');ww=read('BLENDWEIGHTS','get_blendweights')
                pal=unit.skins[0].node_indices.index(ns[prefix+str(k)])
                w=np.where(jj==pal,ww,0).sum(1);sel=w>.01;points.extend(pp[sel]);weights.extend(w[sel])
            pts=np.asarray(points);ta=(tar[2]-tar[0]);ta/=np.linalg.norm(ta)
            rows.append({'node':k,'quantiles_mm':(np.quantile((pts-tar[0])@ta,[0,.1,.5,.9,1])*1000).tolist(),'weighted_mean_mm':float(np.average((pts-tar[0])@ta,weights=weights)*1000)})
        report[side]['refs'][asset]=rows
print('HAND_WEIGHT_AXIAL',json.dumps(report))
