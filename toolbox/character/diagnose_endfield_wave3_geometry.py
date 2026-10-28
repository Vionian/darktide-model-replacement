import pathlib,sys,json,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
out=pathlib.Path(__file__).parent/'endfield_batch'
report={}
for key in ('aitela','saixi'):
    report[key]={}
    for asset in (key,key+'_arms'):
        folder=out/key/'Custom'/asset
        unit=b.unit_dt.UnitResourceDT(b.Cursor(str(folder/(asset+'.unit'))))
        rows=[]
        for index,g in enumerate(unit.mesh_geometries):
            normal=b.mesh_geometry.math_utils.octahedral_decode(g.streams[2].vertex_data)
            packed=np.frombuffer(g.streams[0].vertex_data,'<f2').reshape(-1,4)
            tangent=b.mesh_geometry.math_utils.octahedral_decode(packed[:,:2].copy().tobytes())
            bitangent=b.mesh_geometry.math_utils.octahedral_decode(packed[:,2:].copy().tobytes())
            dots=np.abs((normal*tangent).sum(1));bdots=np.abs((normal*bitangent).sum(1))
            bad=np.flatnonzero((dots>.015)|(bdots>.015))
            rows.append({'geo':index,
                'vertices':len(normal),'tangent_max':float(dots.max()),
                'bitangent_max':float(bdots.max()),
                'bad_tangents':int((dots>.015).sum()),'bad_bitangents':int((bdots>.015).sum()),
                'examples':[{'vertex':int(v),'normal':normal[v].tolist(),'tangent':tangent[v].tolist(),
                    'bitangent':bitangent[v].tolist(),'packed':packed[v].tolist()}for v in bad[:3]]})
        report[key][asset]=rows
print('GEOMETRY_DIAGNOSTIC',json.dumps(report))
(out/'wave3_geometry_diagnostic.json').write_text(json.dumps(report,indent=2),encoding='utf8')
