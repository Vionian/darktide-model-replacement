"""Recompile only calibrated diffuse resources; prove all unit/1P files unchanged."""
import bpy,pathlib,sys,json,numpy as np,hashlib,shutil,datetime
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from endfield_profiles import apply
from endfield_wave2 import PROFILES
out=pathlib.Path(__file__).parent/'endfield_batch'
measure=json.loads((out/'wave2_color_measurements.json').read_text(encoding='utf-8'))
requested=sys.argv[sys.argv.index('--')+1:]if'--'in sys.argv else list(PROFILES)
calibration_path=out/'wave2_color_calibration.json'
calibration=(json.loads(calibration_path.read_text(encoding='utf-8'))if calibration_path.exists()else
    {k:{'face_linear_gain':np.clip(1+(np.asarray(v['face_linear_gain'])-1)*.65,.80,1.05).tolist(),
        'hair_linear_gain':v['hair_linear_gain'],'reference':v['reference'],
        'method':'bounded screenshot ROI calibration; not recovered shader constants'}for k,v in measure.items()})
report={};backup=out/('wave2_color_backup_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for key in requested:
    if key not in PROFILES:raise ValueError('Unknown Endfield profile: '+key)
    p=PROFILES[key]
    dest=out/key;folder=dest/'Custom'/key
    # Exclude authoring PNG/DDS caches; all compiled 1P bytes must stay exact.
    arms=dest/'Custom'/(key+'_arms')
    before_arms={str(f.relative_to(arms)):sha(f)for f in arms.rglob('*')if f.is_file()and 'source_textures'not in f.parts}
    before_unit=sha(folder/(key+'.unit'))
    shutil.copytree(folder,backup/key)
    apply(b,key);b.HAND_AUTHORING_OUTPUT=dest
    bpy.ops.wm.open_mainfile(filepath=str(b.SOURCE_BLEND))
    mesh=bpy.data.objects[b.MESH_OBJECT_NAME];arm=bpy.data.objects[b.ARMATURE_OBJECT_NAME];b.prepare_source(mesh,arm)
    changed=[]
    for i,mat in enumerate(mesh.data.materials):
        from endfield_face_materials import FACE_LAYERS
        if mat.name not in FACE_LAYERS|{'发','尾巴','尾'}:continue
        alpha=b.material_is_alpha(i,mat.name);channel='bca'if alpha else 'bc'
        resource=f'{b.RESOURCE_ROOT}/{key}_material_{i}_{channel}'
        if not(folder/(resource.rsplit('/',1)[-1]+'.texture')).exists():continue
        _,_,pixels,srgb=b.image_pixels_for(mat)
        pixels=pixels.copy()
        assert srgb,'Source diffuse is expected to be byte sRGB'
        if not alpha:pixels[:,:,3]=1
        b.write_texture(folder,resource,pixels,'BC3_UNORM_SRGB'if alpha else 'BC1_UNORM_SRGB')
        changed.append({'index':i,'material':mat.name,'resource':resource,
                        'diffuse_source':'See source_color_calibration.json: source diffuse or UV-verified CMB albedo'})
    manifest=folder/'build.json';data=json.loads(manifest.read_text(encoding='utf-8'))
    for a in data['artifacts']:a['size']=(folder/a['path']).stat().st_size
    manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert before_unit==sha(folder/(key+'.unit'))
    assert all(sha(arms/rel)==v for rel,v in before_arms.items())
    report[key]={'calibration':calibration[key],'changed_diffuse_resources':changed,'body_unit_unchanged':True,'all_first_person_resources_unchanged':True}
    print('WAVE2_COLOR_REFRESH',key,changed,flush=True)
(out/'wave2_color_refresh_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('WAVE2_COLOR_REFRESH_DONE',backup,flush=True)
