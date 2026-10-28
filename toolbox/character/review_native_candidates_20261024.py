"""Create current-build contact sheets and explicitly recorded offline reviews."""
from pathlib import Path
import argparse,datetime,json
from PIL import Image,ImageDraw,ImageFont
from repair_native_hands_20261024 import REPAIR,OUT,LEGACY,fingerprints
from deploy_native_hand_repair_20261024 import sha

def candidate(tag):
    result=json.loads((REPAIR/tag/'complete_candidate.json').read_text(encoding='utf8'))
    assert result['build']['pipeline_sha256']==fingerprints(),('Stale candidate',tag)
    folder=REPAIR/tag if tag in LEGACY else OUT/tag
    unit=folder/'Custom'/(tag+'_arms')/(tag+'_arms.unit')
    images=[]
    for pose in result['preview']['poses']:
        for name in pose['images']:
            p=Path(name);assert p.is_file()and p.stat().st_mtime>=unit.stat().st_mtime,('Stale image',p)
            images.append(dict(path=str(p),sha256=sha(p),pose=pose['pose']))
    return result,images

def sheet(tags,name):
    font=ImageFont.truetype('<WINDOWS_FONTS>/arial.ttf',18)
    canvas=Image.new('RGB',(1440,460*len(tags)),(30,34,40));draw=ImageDraw.Draw(canvas)
    for row,tag in enumerate(tags):
        _,images=candidate(tag)
        draw.text((12,row*460+5),tag,fill='white',font=font)
        for i,entry in enumerate(images):
            im=Image.open(entry['path']).convert('RGB');im.thumbnail((360,420))
            x=i*360;y=row*460+35
            canvas.paste(im,(x+(360-im.width)//2,y))
            hand='left'if '_left_'in entry['path']else 'right'
            draw.text((x+10,y),entry['pose']+' / '+hand,fill='#E6C267',font=font)
    output=REPAIR/(name+'.jpg');canvas.save(output,quality=94)
    print(str(output));return output

def approve(tags,note):
    for tag in tags:
        result,images=candidate(tag)
        report=dict(profile=tag,approved_offline=True,reviewed_at=datetime.datetime.now().isoformat(),
            build_started_at=result['build']['started_at'],pipeline_sha256=fingerprints(),images=images,
            visual_notes=note,gameplay_verified=False,
            limits='Static source and synthetic production-Lua poses; no original-game motion capture or gameplay action coverage')
        (REPAIR/tag/'visual_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print('OFFLINE_VISUAL_REVIEW_RECORDED',tag)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('tags',nargs='+');p.add_argument('--sheet',default='current_candidate_review')
    p.add_argument('--approve-note');args=p.parse_args()
    if args.approve_note:approve(args.tags,args.approve_note)
    else:sheet(args.tags,args.sheet)
