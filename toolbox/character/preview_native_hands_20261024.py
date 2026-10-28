"""Use existing serialized resource verifier with smaller diagnostic renders."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
path=HERE/'preview_roshia_native.py'
source=path.read_text(encoding='utf8')
anchor='np.save(OUT / "roshia_builder_retargeted_positions.npy", builder_positions)'
assert anchor in source
source=source.replace(anchor,anchor+'\nfrom costume_surface_edge_audit import record as record_surface_edges\nrecord_surface_edges(builder,mesh,builder_positions,OUT/"fitted_surface_edge_audit.json")')
anchor='if args.serialized_geometry:'
hook='''
original_diagnostic_collect=builder.collect_triangles
def diagnostic_collect(*a,**kw):
    groups=original_diagnostic_collect(*a,**kw)
    record_surface_edges(builder,a[0],groups[0]['retargeted_positions'],OUT/"exported_surface_edge_audit.json",groups)
    selected=[];materials=[]
    for mi,g in enumerate(groups):
        if len(g['triangles']):
            selected.extend(g['vertices'][g['triangles']].tolist())
            materials.extend([mi]*len(g['triangles']))
    np.savez_compressed(OUT/"actual_source_face_selection.npz",
        source_positions=np.asarray([a[0].matrix_world@v.co for v in a[0].data.vertices]),
        fitted_positions=groups[0]['retargeted_positions'],faces=np.asarray(selected),materials=np.asarray(materials))
    return groups
builder.collect_triangles=diagnostic_collect
'''
source=source.replace(anchor,hook+'\n'+anchor,1)
for old,new in [('scene.render.resolution_x = 1200','scene.render.resolution_x = 720'),
                ('scene.render.resolution_y = 1400','scene.render.resolution_y = 840'),
                ('scene.eevee.taa_render_samples = 128','scene.eevee.taa_render_samples = 32')]:
    assert old in source,old
    source=source.replace(old,new)
exec(compile(source,str(path),'exec'),{'__name__':'__main__','__file__':str(path)})
