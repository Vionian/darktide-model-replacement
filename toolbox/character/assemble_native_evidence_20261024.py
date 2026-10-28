"""Contact sheets for current serialized action/body reviews, never stale images."""
from pathlib import Path
import sys,json,hashlib
from PIL import Image,ImageDraw,ImageFont
from repair_native_hands_20261024 import REPAIR,OUT,LEGACY
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def assemble(tag):
 base=REPAIR/tag if tag in LEGACY else OUT/tag
 arms=base/'Custom'/(tag+'_arms')/(tag+'_arms.unit')
 body=base/'Custom'/tag/(tag+'.unit')
 groups=[]
 action=REPAIR/tag/'action_checks.json'
 if action.exists():
  a=json.loads(action.read_text(encoding='utf8'))
  if a.get('unit_sha256')==sha(arms):
   for p in a['poses']:groups.append((p['pose'],p['images']))
 for path in sorted((REPAIR/tag).glob('body_*/checks.json')):
  d=json.loads(path.read_text(encoding='utf8'))
  if d.get('unit_sha256')==sha(body):groups.append((d['focus'],d['images']))
 assert groups,('No current evidence',tag)
 font=ImageFont.truetype('<WINDOWS_FONTS>/arial.ttf',18)
 canvas=Image.new('RGB',(1440,460*len(groups)),(30,34,40));draw=ImageDraw.Draw(canvas)
 for row,(label,files)in enumerate(groups):
  draw.text((10,row*460+6),tag+' / '+label,fill='white',font=font)
  for col,p in enumerate(files):
   im=Image.open(p).convert('RGB');im.thumbnail((360,420))
   canvas.paste(im,(col*360+(360-im.width)//2,row*460+35))
 out=REPAIR/(tag+'_current_action_body.jpg');canvas.save(out,quality=95)
 print(out)
for tag in sys.argv[1:]:assemble(tag)
