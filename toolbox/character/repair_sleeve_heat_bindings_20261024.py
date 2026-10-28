"""Rebind generated garment arm domains to their actual original arm bones.

No hand topology/weights, geometry, UVs, images, or author buffers are edited.
Temporary welding is used only by Blender's heat solver.
"""
from pathlib import Path
import bpy,bmesh,numpy as np,json,sys,shutil,hashlib
from mathutils.kdtree import KDTree
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from costume_anatomical_domains import nearest,from_armature,is_arm
def run(tag,apply=False):
    legacy={'si_short_skirt':HERE/'si_costumes/si_short_skirt/si_short_skirt.blend',
            'si_lolita':HERE/'si_costumes/si_lolita/si_lolita.blend',
            'si_ink_mist':HERE/'si_ink_mist/si_ink_mist.blend'}
    source=legacy.get(tag,HERE/'skins_20261023'/tag/(tag+'.blend'))
    base='si'if tag.startswith('si_')else json.loads((source.parent/'conversion.json').read_text())['base']
    meta=json.loads((HERE/'skins_20261023/references'/base/'source.json').read_text(encoding='utf8'))
    out=HERE/'hand_repair_20261024'/tag;out.mkdir(exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source));mesh=bpy.data.objects[meta['mesh']];arm=bpy.data.objects[meta['armature']]
    p=np.array([mesh.matrix_world@v.co for v in mesh.data.vertices]);domain=nearest(p,from_armature(arm))
    garment={i for i,m in enumerate(mesh.data.materials)if m and not m.get('costume_skin')and (m.name.startswith('Costume_')or m.name.startswith('InkMist_'))}
    regional=np.array([is_arm(str(n))for n in domain])
    faces=[list(f.vertices)for f in mesh.data.polygons if f.material_index in garment and regional[list(f.vertices)].all()]
    ids=sorted({i for f in faces for i in f});assert len(ids)>100,(tag,'Missing actual sleeve surface')
    index={vi:j for j,vi in enumerate(ids)}
    data=bpy.data.meshes.new('__sleeve_heat_donor');data.from_pydata([mesh.data.vertices[i].co for i in ids],[],[[index[i]for i in f]for f in faces]);data.update()
    donor=bpy.data.objects.new(data.name,data);bpy.context.collection.objects.link(donor);donor.matrix_world=mesh.matrix_world.copy()
    bm=bmesh.new();bm.from_mesh(data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(data);bm.free();data.update()
    rig=arm.copy();rig.data=arm.data.copy();bpy.context.collection.objects.link(rig);rig.animation_data_clear()
    actual={s+'.'+side for s in ('肩','腕','ひじ','肘','手首')for side in ('L','R')}
    for bone in rig.data.bones:bone.use_deform=bone.name in actual
    for bone in rig.pose.bones:
        for c in list(bone.constraints):bone.constraints.remove(c)
        bone.matrix_basis.identity()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in (donor,rig):obj.hide_viewport=False;obj.hide_set(False);obj.select_set(True)
    bpy.context.view_layer.objects.active=rig;bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    names={g.index:g.name for g in donor.vertex_groups};tree=KDTree(len(data.vertices))
    for v in data.vertices:tree.insert(v.co,v.index)
    tree.balance();result=[]
    for vi in ids:
        _,i,distance=tree.find(mesh.data.vertices[vi].co);assert distance<3e-6,(tag,vi,distance)
        weights={names[g.group]:float(g.weight)for g in data.vertices[i].groups if g.weight>1e-7}
        total=sum(weights.values());assert total>.5,('Bone heat did not solve sleeve',tag,vi,total)
        result.append((vi,{n:w/total for n,w in weights.items()}))
    if apply:
        backup=out/'before_sleeve_heat_rebind.blend';assert not backup.exists(),('Existing sleeve repair; do not repeat',tag)
        shutil.copy2(source,backup);old_names={g.index:g.name for g in mesh.vertex_groups}
        for vi,weights in result:
            for g in list(mesh.data.vertices[vi].groups):
                if old_names[g.group]in arm.data.bones:mesh.vertex_groups[g.group].remove([vi])
            for name,w in weights.items():(mesh.vertex_groups.get(name)or mesh.vertex_groups.new(name=name)).add([vi],w,'REPLACE')
        bpy.data.objects.remove(donor,do_unlink=True);bpy.data.objects.remove(rig,do_unlink=True);bpy.data.meshes.remove(data)
        bpy.context.view_layer.objects.active=mesh;bpy.ops.wm.save_as_mainfile(filepath=str(source))
    report=dict(profile=tag,applied=apply,method='Blender ARMATURE_AUTO on measured garment arm domains using actual same-character shoulder/upper-arm/forearm/wrist bones',
        vertices=len(ids),faces=len(faces),source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        geometry_uv_normals_textures_hand_skin_unchanged=True,author_source_files_untouched=True,gameplay_verified=False)
    (out/('sleeve_heat_rebind.json'if apply else 'sleeve_heat_probe.json')).write_text(json.dumps(report,indent=2),encoding='utf8')
    print('SLEEVE_BONE_HEAT',json.dumps(report),flush=True)
if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:];run(args[0],'--apply'in args)
