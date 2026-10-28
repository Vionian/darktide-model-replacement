from pathlib import Path
import json,re,struct
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).parent/'skins_20261023'
rows=json.loads((HERE/'inventory.json').read_text(encoding='utf-8'))
font=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',22)
sheet=Image.new('RGB',(1440,4*470),(28,30,35))
draw=ImageDraw.Draw(sheet)
for index,row in enumerate(rows):
    root=Path(row['path']);lines=[]
    previews=[root/f['path'] for f in row['files'] if '预览' in f['path'] and f['path'].endswith('.png')]
    if previews:
        im=Image.open(previews[0]).convert('RGB');im.thumbnail((460,420))
        x=(index%3)*480; y=(index//3)*470
        sheet.paste(im,(x+(460-im.width)//2,y+40))
        draw.text((x+10,y+5),row['name'],font=font,fill='white')
    for entry in row['files']:
        f=root/entry['path']
        if f.suffix.lower()=='.ini' and not any(s in str(f).casefold() for s in ('backup','menu','panel','ibskip','crossib','cutoutmask')):
            text=f.read_text(encoding='utf-8-sig',errors='replace')
            blocks=re.split(r'^\[([^\]]+)\]\s*$',text,flags=re.M)
            lines.extend(['FILE '+str(f),'BEGIN HEAD',text[:4500],'END HEAD'])
            # Bound summary to actual geometry commands, not thousands of UI blocks.
            for k in range(1,len(blocks),2):
                name,body=blocks[k:k+2]
                if name in ('Constants','Present') or ('drawindexed' in body and not name.startswith('CustomShader')):
                    lines.extend(['['+name+']',body[:7000]])
            lines.extend(['RESOURCES'])
            for k in range(1,len(blocks),2):
                name,body=blocks[k:k+2]
                if name.startswith('Resource'):
                    lines.extend(['['+name+']',body[:450]])
    if row['name']=='水墨-祀':
        for f in [root/e['path'] for e in row['files']][:12]:
            lines.append(str(f)+' HEADER '+repr(f.read_bytes()[:128]))
    (HERE/(row['name']+'_source.txt')).write_text('\n'.join(lines),encoding='utf-8')
sheet.save(HERE/'source_previews.jpg',quality=90)
print('SOURCE_SUMMARIES_READY',len(rows))
