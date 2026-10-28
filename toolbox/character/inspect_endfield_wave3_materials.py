"""Inspect supplied CMB graphs and opacity at the third batch's actual UVs."""
import pathlib
import sys
import json
import hashlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
path = pathlib.Path(__file__).with_name('inspect_endfield_wave2_materials.py')
text = path.read_text(encoding='utf-8')
text = text.replace('from endfield_wave2 import PROFILES', 'from endfield_wave3 import PROFILES')
text = text.replace('wave2_material_inspection.json', 'wave3_material_inspection.json')
text = text.replace('WAVE2_', 'WAVE3_')
exec(compile(text, str(path), 'exec'), globals())
from endfield_wave3 import PROFILES
source_audit = {}
for key, profile in PROFILES.items():
    blend = pathlib.Path('<SOURCE_ROOT>/Rossia') / (profile['name'] + '.blend')
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    mesh = bpy.data.objects[profile['name'] + '_mesh']
    arm = bpy.data.objects[profile['name'] + '_arm']
    gn = {g.index: g.name for g in mesh.vertex_groups}
    names = set(arm.data.bones.keys())
    canonical = [stem + side for side in ('.L', '.R') for stem in
        ['手首', '親指０', '親指１', '親指２'] +
        [d + n for d in ('人指', '中指', '薬指', '小指') for n in ('１', '２', '３')]]
    assert all(n in names for n in canonical), (key, 'Missing original hand bones')
    layers = []
    for index, material in enumerate(mesh.data.materials):
        verts = {vi for poly in mesh.data.polygons if poly.material_index == index for vi in poly.vertices}
        mass = {}
        for vi in verts:
            for group in mesh.data.vertices[vi].groups:
                name = gn[group.group]
                if name in names:
                    mass[name] = mass.get(name, 0.) + group.weight
        normals = [list(mesh.data.vertices[vi].normal) for vi in verts]
        proxy = bpy.data.objects.get(mesh.name + '__' + material.name)
        params = []
        if proxy:
            from character_material_bridge_user import core
            for pm in proxy.data.materials:
                snapshot = core.read_material_column(pm)
                if snapshot:
                    part, col, width, data = snapshot
                    wanted = ('color', 'alpha', 'opacity', 'cutoff', 'fur', 'smooth', 'metal', 'bump')
                    params.append({n: core.read_param(data, width, col, part, n)
                        for n in core.param_names(part) if any(t in n.lower() for t in wanted)})
        layers.append({'index': index, 'name': material.name,
            'dominant_bones': sorted(mass.items(), key=lambda x: -x[1])[:6],
            'mean_normal': np.mean(normals, axis=0).tolist() if normals else None,
            'authored_parameters': params,
            'main_images': [{'node': n.name, 'image': n.image.name, 'size': list(n.image.size)}
                for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
                if material.node_tree else []})
    pmx = next(profile['source_dir'].glob('*.pmx'))
    source_audit[key] = {'source_blend': str(blend),
        'blend_sha256': hashlib.sha256(blend.read_bytes()).hexdigest(),
        'source_pmx': str(pmx), 'pmx_sha256': hashlib.sha256(pmx.read_bytes()).hexdigest(),
        'canonical_source_hand_joints': canonical,
        'source_actions': list(bpy.data.actions.keys()), 'materials': layers}
(out / 'wave3_source_contract.json').write_text(json.dumps(source_audit, ensure_ascii=False, indent=2), encoding='utf8')
print('WAVE3_SOURCE_CONTRACT_DONE', flush=True)
