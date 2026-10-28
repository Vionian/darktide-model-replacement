import importlib.util, pathlib, sys, json, traceback
import bpy, numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[2]
folder=ROOT/'tools/hd2-reference-reader'
spec=importlib.util.spec_from_file_location('hd2_reader',folder/'__init__.py',submodule_search_locations=[str(folder)])
hd=importlib.util.module_from_spec(spec);sys.modules[spec.name]=hd;spec.loader.exec_module(hd)
hd.LoadNormalPalette(hd.Global_palettepath)
bpy.utils.register_class(hd.Hd2ToolPanelSettings)
bpy.types.Scene.Hd2ToolPanelSettings=bpy.props.PointerProperty(type=hd.Hd2ToolPanelSettings)
bpy.context.scene.Hd2ToolPanelSettings.ImportMaterials=False
# Current HD2 units moved vertex-format enum values. Mapping verified against
# HD2SDK-AQ-Edition/stingray/unit.py, StreamComponentFormat (version >= 130).
original_component=hd.StreamComponentInfo.SerializeComponent
def read_component(self,f,value):
    old=self.Format
    self.Format={24:20,28:24,29:25,30:26,33:29,35:31}.get(old,old)
    try:return original_component(self,f,value)
    finally:self.Format=old
hd.StreamComponentInfo.SerializeComponent=read_component
source=ROOT/'tools/model-work/roshia/hd2_reference/extracted'
report=[]
for path in source.glob('*.unit'):
    try:
        gpu=pathlib.Path(str(path)+'.gpu')
        obj=hd.LoadStingrayMesh(int(path.stem,16),path.read_bytes(),gpu.read_bytes() if gpu.exists() else b'',b'',False,False)
        meshes=[]
        for i,m in enumerate(obj.RawMeshes):
            p=np.asarray(m.VertexPositions,dtype=float)
            if len(p)==0:continue
            np.savez_compressed(source/f'{path.stem}_mesh_{i}.npz',positions=p,normals=np.asarray(m.VertexNormals),faces=np.asarray(m.Indices),uv=np.asarray(m.VertexUVs),weights=np.asarray(m.VertexWeights),joints=np.asarray(m.VertexBoneIndices))
            meshes.append({'index':i,'lod':m.LodIndex,'vertices':len(p),'faces':len(m.Indices),'bounds':[p.min(axis=0).tolist(),p.max(axis=0).tolist()], 'materials':[str(x.MatID) for x in m.Materials]})
        report.append({'unit':path.name,'meshes':meshes,'materials':obj.MaterialIDs,'bone_counts':[x.NumBones for x in obj.BoneInfoArray]})
        print('HD2_MESH',path.name,len(meshes))
    except Exception as e:
        report.append({'unit':path.name,'error':repr(e)});traceback.print_exc()
(source/'mesh_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
