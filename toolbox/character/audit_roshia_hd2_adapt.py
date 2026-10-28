import pathlib, json, sys, struct
import numpy as np
import bpy
from mathutils import Matrix, Vector
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_roshia_native as b
ROOT = b.ROOT
OUT = ROOT / 'tools/model-work/roshia/hd2_adapt_candidate'
if '--' in sys.argv and len(sys.argv)>sys.argv.index('--')+1:
    OUT=pathlib.Path(sys.argv[sys.argv.index('--')+1]).resolve()
template = b.load_target_unit()
names = b.named_node_map(template, b.BonesResourceDT(b.Cursor(str(b.TEMPLATE/'qianxia_bones.bones'))))
result = {}
fixture = {'names': names, 'template_world': [b.matrix_column_major(n.world_transform) for n in template.scene_graph.nodes],
           'parents': [n.parent_index if n.parent_type == b.ParentType.INTERNAL else -1 for n in template.scene_graph.nodes]}
for asset in ('roshia', 'roshia_arms'):
    folder = OUT/'Custom'/asset
    unit = b.unit_dt.UnitResourceDT(b.Cursor(str(folder/(asset+'.unit'))))
    if asset == 'roshia_arms':
        config=json.loads((OUT/'Custom/roshia_proportion_bones.json').read_text())['arms']
        decoded=b.named_node_map(unit,b.BonesResourceDT(b.Cursor(str(folder/(asset+'_bones.bones')))))
        private=[d for d in config['bones'] if d.get('source_hand_fk')]
        assert len(private)==(0 if config.get('native_hand_contract') else 38),len(private)
        if config.get('native_hand_contract'):
            for name,index in names.items():
                if name.startswith(('j_lefthand','j_righthand','j_leftinhand','j_rightinhand')):
                    assert decoded[name]==index
                    assert np.max(np.abs(np.array(unit.scene_graph.nodes[index].world_transform)-np.array(template.scene_graph.nodes[index].world_transform)))<2e-6
                    assert unit.scene_graph.nodes[index].parent_index==template.scene_graph.nodes[index].parent_index
                    slot=unit.skins[0].node_indices.index(index)
                    inv=np.array(unit.skins[0].inv_bind_matrices[slot])
                    assert np.max(np.abs(np.array(unit.scene_graph.nodes[index].world_transform)@inv-np.eye(4)))<2e-5


        for d in private:
            assert d['name'] not in decoded
            assert decoded[d['target_name']]==names[d['name']]
        for side in ('left','right'):
            assert decoded[f'j_{side}hand']==names[f'j_{side}hand']
    fixture[asset] = {'world': [b.matrix_column_major(n.world_transform) for n in unit.scene_graph.nodes],
                      'parents': [n.parent_index if n.parent_type == b.ParentType.INTERNAL else -1 for n in unit.scene_graph.nodes]}
    tangent_dot, bitangent_dot, sphere_margins = [], [], []
    for geo, obj in zip(unit.mesh_geometries, unit.meshes):
        normal = b.mesh_geometry.math_utils.octahedral_decode(geo.streams[2].vertex_data)
        packed = np.frombuffer(geo.streams[0].vertex_data, '<f2').reshape(-1,4)
        tangent = b.mesh_geometry.math_utils.octahedral_decode(packed[:,:2].copy().tobytes())
        minus_b = b.mesh_geometry.math_utils.octahedral_decode(packed[:,2:].copy().tobytes())
        tangent_dot.extend(abs((normal*tangent).sum(axis=1)))
        bitangent_dot.extend(abs((normal*minus_b).sum(axis=1)))
        position_channel=next(c for c in geo.channels if c.component.name=='POSITION')
        p=geo.streams[position_channel.stream].get_positions(position_channel).astype(float)
        box=np.r_[p.min(axis=0),p.max(axis=0)]
        for bound in (geo.bounding_volume, obj.bounding_volume):
            center=np.array([bound.unk1,bound.unk2,bound.unk3]);radius=bound.unk4
            sphere_margins.append(float(radius-np.linalg.norm(p-center,axis=1).max()))
    assert max(tangent_dot)<.015, max(tangent_dot)
    assert max(bitangent_dot)<.015, max(bitangent_dot)
    assert min(sphere_margins)>0
    manifests=json.loads((folder/'build.json').read_text())
    own={b.hash64(a['resource']['name']) for a in manifests['artifacts']}
    alpha_providers=[]
    shader_links=[]
    texture_profiles={}
    for a in manifests['artifacts']:
        if a['resource']['type']=='material' and a['role']=='stream':
            raw=(folder/a['path']).read_bytes(); off=struct.unpack_from('<I',raw,4)[0]
            provider=struct.unpack_from('<Q',raw,off+4)[0]
            parent=struct.unpack_from('<Q',raw,off+12)[0]
            resource_name=a['resource']['name']
            if any(s in resource_name for s in ('_alpha_shader','_material_0','_material_1','_material_2','_material_3','_material_5','_material_13')) and resource_name.rsplit('_',1)[-1] in ('shader','0','1','2','3','5','13') and provider!=b.hash64('content/parent_materials/substance_basic'):
                assert provider in own or provider==0, (resource_name,hex(provider))
                assert parent in own, (resource_name,hex(parent))
                shader_links.append({'name':resource_name,'provider':hex(provider),'parent':hex(parent)})
            # Eye overlays 2/5 are now opaque substance_basic. Only actual
            # custom alpha providers must resolve to a packaged local shader.
            if a['resource']['name'].endswith(('_material_2','_material_5','_material_13')):
                assert provider in own or provider==b.hash64('content/parent_materials/substance_basic'), hex(provider)
                if provider in own:
                    alpha_providers.append(hex(provider))
        if a['resource']['type']=='texture' and a['role']=='primary':
            raw=(folder/a['path']).read_bytes()
            size=struct.unpack_from('<I',raw,29)[0]
            footer=struct.unpack_from('<I',raw,38+size-4)[0]
            suffix=a['resource']['name'].rsplit('_',1)[-1]
            expected={'bc':0xa88c22b7,'bca':0x6bd03744,'nm':0x3390aba5,'orm':0xe514d1dc,'em':0xae01e4bc,
                      'portrait':0x6bd03744}[suffix]
            assert footer==expected,(a['path'],hex(footer),hex(expected))
            texture_profiles[suffix]=hex(footer)
    result[asset]={'max_normal_tangent_dot':float(max(tangent_dot)), 'max_normal_bitangent_dot':float(max(bitangent_dot)),
                   'min_bounds_sphere_margin':min(sphere_margins),'alpha_providers_packaged':alpha_providers,
                   'triangles':sum(g.index_stream.index_count//3 for g in unit.mesh_geometries),
                   'local_shader_links':shader_links,'texture_profiles':texture_profiles}
(OUT/'runtime_fixture.json').write_text(json.dumps(fixture))
(OUT/'asset_audit.json').write_text(json.dumps(result,indent=2))
print('HD2_ADAPT_ASSET_AUDIT',result)
