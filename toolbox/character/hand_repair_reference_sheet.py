from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
root=Path('<SOURCE_ROOT>/Skins')
out=Path(__file__).parent/'hand_repair_20261024'
font=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',20)
paths=[p for p in root.rglob('*') if p.is_file() and p.parent.name=='预览' and p.suffix.lower() in ('.png','.jpg','.webp')]
tiles=[]
for p in paths:
    if p.parent.parent.name=='JK-佩丽卡':continue
    im=Image.open(p).convert('RGB');im.thumbnail((460,340))
    tile=Image.new('RGB',(480,380),(35,35,40));tile.paste(im,((480-im.width)//2,32+(340-im.height)//2))
    ImageDraw.Draw(tile).text((8,4),p.parent.parent.name+' / '+p.stem[:6],font=font,fill='white')
    tiles.append(tile)
sheet=Image.new('RGB',(480*4,380*((len(tiles)+3)//4)),(35,35,40))
for i,tile in enumerate(tiles):sheet.paste(tile,((i%4)*480,(i//4)*380))
sheet.save(out/'supplied_preview_reference_sheet.jpg',quality=90)
print(out/'supplied_preview_reference_sheet.jpg',len(tiles))
