import importlib.util, json, pathlib, sys
import bpy
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/model-work'))
import build_roshia_native as b
b.material_module.EXPECTED_MATERIAL_VERSIONS_DT.add(62)
OUT=ROOT/'tools/model-work/roshia/hd2_adapt_candidate'
OUT.mkdir(parents=True,exist_ok=True)
report={}
skin_report={}
for folder in ('qianxia','daniya_blue','daniya_blue_arms','roshia'):
    u=b.unit_dt.UnitResourceDT(b.Cursor(str(ROOT/'Custom'/folder/(folder+'.unit'))))
    skin_report[folder]={'palettes':[{'nodes':s.node_indices,'sets':s.matrix_index_sets} for s in u.skins], 'meshes':[vars(m) for m in u.meshes]}
(OUT/'skin_sets.json').write_text(json.dumps(skin_report,default=str,indent=2),encoding='utf-8')
for folder in ('qianxia','daniya_blue','daniya_blue_arms','roshia'):
    b.material_module.load_stream_dt=lambda p,folder=folder:b.StreamReader(b.Cursor(str(ROOT/'Custom'/folder/p)))
    data={}
    for path in (ROOT/'Custom'/folder).glob('*.material'):
        mat=b.MaterialResourceDT(b.Cursor(str(path)))
        data[path.name]=mat.json_dump()
    report[folder]=data
(OUT/'material_diagnostics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
mesh=bpy.data.objects[b.MESH_OBJECT_NAME]; arm=bpy.data.objects[b.ARMATURE_OBJECT_NAME]
report={'materials':[(i,m.name) for i,m in enumerate(mesh.data.materials)]}
unit=b.load_target_unit(); names=b.named_node_map(unit,b.BonesResourceDT(b.Cursor(str(b.TEMPLATE/'qianxia_bones.bones'))))
records={};b.target_bind_transforms(arm,names,unit,node_records=records,mesh=mesh)
report['pivots']={r['name']:{'source':list(r['world'].translation),'template':list(unit.scene_graph.nodes[i].world_transform.translation)} for i,r in records.items()}
(OUT/'source_pivots.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('DIAGNOSTICS',str(OUT))
