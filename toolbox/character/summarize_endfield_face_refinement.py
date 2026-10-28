"""Evidence for the eight-profile face pass, with fixed before/after framing."""
import pathlib,json,hashlib,datetime
from PIL import Image,ImageOps,ImageDraw,ImageFont,ImageChops
from endfield_wave2 import PROFILES,REFERENCE_IMAGES
HERE=pathlib.Path(__file__).parent;OUT=HERE/'endfield_batch';DEST=OUT/'face_refinement'
font=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',24)
small=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',19)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def native_crop(p):
 im=Image.open(p).convert('RGB');w,h=im.size
 return im.crop((int(w*.26),int(h*.38),int(w*.74),int(h*.77)))
def source_crop(key):
 im=Image.open(pathlib.Path(r'<SOURCE_ROOT>\终末地')/(REFERENCE_IMAGES[key]+'.png')).convert('RGB')
 w,h=im.size
 return im.crop((int(w*.32),int(h*.11),int(w*.68),int(h*.31)))
def place(canvas,im,box):
 x,y,w,h=box;im=ImageOps.contain(im,(w,h))
 canvas.paste(im,(x+(w-im.width)//2,y+(h-im.height)//2))
baseline=json.loads((DEST/'deployed_arms_baseline.json').read_text(encoding='utf8'))
calibration=json.loads((OUT/'wave2_color_calibration.json').read_text(encoding='utf8'))
sheet=Image.new('RGB',(1800,2080),'#20262e');draw=ImageDraw.Draw(sheet)
report={}
for i,(key,profile)in enumerate(PROFILES.items()):
 x=i%2*900;y=i//2*510
 draw.text((x+15,y+12),profile['name'],font=font,fill='white')
 before=DEST/'before'/(key+'.png')
 final=OUT/key/'final_face/roshia_preunit_matrix_hand_rigid_face_front_preview.png'
 log=(OUT/key/'final_face.log').read_text(encoding='utf8')
 assert 'PREVIEW_UNIT_GEOMETRY_MATCH'in log and 'PREUNIT_PREVIEW'in log,key
 for j,(label,im)in enumerate((('提供的原版参考',source_crop(key)),('上轮导出',native_crop(before)),('本轮导出',native_crop(final)))):
  draw.text((x+j*300+12,y+53),label,font=small,fill='#cbd9e2')
  place(sheet,im,(x+j*300+8,y+90,284,390))
 arms=OUT/key/'Custom'/(key+'_arms')
 changed=[n for n,h in baseline[key].items()if not(arms/n).exists()or sha(arms/n)!=h]
 assert not changed,(key,'First-person regression',changed)
 bake=json.loads((DEST/key/'albedo_report.json').read_text(encoding='utf8'))
 assert all(r.get('outline_excluded')and r.get('explicit_lookup_uv')and r.get('lighting_baked')is False for r in bake),key
 for row in bake:assert sha(DEST/key/row['file'])==row['sha256'],(key,row['file'])
 exported_colors=json.loads((OUT/key/'source_color_calibration.json').read_text(encoding='utf8'))
 selected_bakes={name:row for name,row in exported_colors.items()if row.get('baked_sha256')}
 if key=='liino':
  assert '睫眉'not in selected_bakes and '口内'not in selected_bakes
  assert all(selected_bakes[n].get('source_style_lighting_baked')is False for n in selected_bakes)
 for asset in (key,key+'_arms'):
  root=OUT/key/'Custom'/asset;manifest=json.loads((root/'build.json').read_text(encoding='utf8'))
  for entry in manifest['artifacts']:assert(root/entry['path']).stat().st_size==entry['size']
 difference=ImageChops.difference(Image.open(before).convert('RGB'),Image.open(final).convert('RGB'))
 assert difference.getbbox(),(key,'No visible change')
 report[key]={'name':profile['name'],'face_preview':str(final.resolve()),'preview_sha256':sha(final),
  'calibration':calibration[key],'compiled_first_person_files_unchanged':len(baseline[key]),
  'albedo_layers':len(bake),'compiled_geometry_and_native_textures_readback':True,
  'selected_unlit_bake_layers':list(selected_bakes),
  'source_diffuse_fallback_layers':['睫眉','口内']if key=='liino'else [],
  'full_outline_shell_exported':False,'fixed_lighting_eye_bake_used':False,'gameplay_verified':False}
draw.text((15,2040),'相同灯光的导出前后对比；原版参考环境不同。图片为编译资源回读预览，非暗潮实机截图。',font=small,fill='#cbd9e2')
sheet.save(DEST/'eight_faces_refined.png')
detail=Image.new('RGB',(1800,820),'#20262e');dd=ImageDraw.Draw(detail)
key='zhuangfangyi'
for j,(label,im)in enumerate((('原版参考',source_crop(key)),('上轮',native_crop(DEST/'before'/f'{key}.png')),
 ('本轮',native_crop(OUT/key/'final_face/roshia_preunit_matrix_hand_rigid_face_front_preview.png')))):
 dd.text((j*600+20,20),label,font=font,fill='white');place(detail,im,(j*600+10,70,580,700))
dd.text((20,785),'庄方宜：独立肤色与眼部层次校准；保留原模中性表情，未更改脸型。',font=small,fill='#cbd9e2')
detail.save(DEST/'zhuangfangyi_face_before_after.png')
result={'created_at':datetime.datetime.now().isoformat(),'profiles':report,
 'limits':['No in-game launch or gameplay validation','Native PBR is not a full Endfield toon-shader port',
 'Art-direction color gains are separate from recovered source material values']}
(DEST/'face_refinement_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print('FACE_REFINEMENT_DELIVERY',len(report),'profiles; first-person compiled files unchanged',sum(len(v)for v in baseline.values()))
