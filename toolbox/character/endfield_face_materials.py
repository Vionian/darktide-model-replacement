"""Read UV-verified, unlit CMB albedo bakes used by build and preview alike."""
import pathlib,json,hashlib,numpy as np
ROOT=pathlib.Path(__file__).parent/'endfield_batch/face_refinement'
FACE_LAYERS={'面','目','目1','目2','目白','睫','眉','睫眉','二重','目HL','目1HL','目2HL','口','口内'}

def albedo(b,key,name):
    if name not in FACE_LAYERS and name not in getattr(b,'CMB_ALBEDO_MATERIALS',set()):return None
    # Liino's CMB diagnostic output is identically black for these two
    # branches, unlike the supplied diffuse (purple lashes / mouth detail).
    # Keep the source texture rather than shipping a false black bake.
    if key=='liino'and name in ('睫眉','口内'):return None
    folder=ROOT/key;report=folder/'albedo_report.json'
    if not report.exists():return None
    rows=json.loads(report.read_text(encoding='utf-8'))
    row=next((r for r in rows if r['material']==name and r.get('lighting_baked')is False),None)
    style=folder/'eye_style_report.json'
    if getattr(b,'CMB_EYE_STYLE',False)and name!='面'and style.exists():
        styled=next((r for r in json.loads(style.read_text(encoding='utf8'))
                     if r['material']==name and r.get('bake_kind')=='CMB fixed authoring eye ramp/matcap color'),None)
        if styled:row=styled
    if row is None:return None
    path=folder/row['file']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
        raise ValueError('Stale CMB albedo: '+str(path))
    image=b.bpy.data.images.load(str(path),check_existing=False)
    image.colorspace_settings.name='sRGB'
    w,h=image.size;pixels=np.empty(w*h*4,np.float32);image.pixels.foreach_get(pixels)
    return w,h,pixels.reshape(h,w,4),row
