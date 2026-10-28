from pathlib import Path
import sys,json,struct
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from skins_sources import source,OUT,SOURCES
from efmi_draws import Reader

def fields(file):
    b=Path(file).read_bytes();assert b[:8]==b'EFFRES2\0'
    o=80;out={}
    for i in range(struct.unpack_from('<I',b,16)[0]):
        n=struct.unpack_from('<H',b,o)[0];o+=2;name=b[o:o+n].decode();o+=n
        start,size=struct.unpack_from('<QQ',b,o);o+=48;out[name]=b[start:start+size]
    return out

if __name__=='__main__':
    font=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',14)
    for key in SOURCES:
        spec=source(key)
        if key=='si_ink_wash':
            f=next(spec['folder'].rglob('*.mesh'));fs=fields(f);v=fs['m_VertexData']
            print('EFF_VERTEX',struct.unpack_from('<2I',v),[tuple(v[8+i*4:12+i*4])for i in range(14)])
            print('EFF_SUB',fs['m_SubMeshes'][:100].hex(),'BONES',fs['@bones'][:250])
            print('EFF_TEXTURES',[(p.name,struct.unpack_from('<5I',fields(p)['@texture']))for p in spec['folder'].rglob('*.tex')])
            continue
        r=Reader(spec['ini']);paths=sorted({r.path(n)for n,x in r.resources.items()if r.path(n)and r.path(n).suffix.lower()in ('.dds','.png')and not any(t in r.path(n).name.lower()for t in ('slot','menu','logo','icon'))and r.path(n).parent.name.casefold()!='res'})
        tiles=[]
        for p in paths:
            try:
                im=Image.open(p).convert('RGBA');tile=Image.new('RGB',(220,255),'#333333');im.thumbnail((215,210));tile.paste(im,((220-im.width)//2,5),im)
                d=ImageDraw.Draw(tile);label=p.name
                if len(label)>32:label=label[:29]+'...'
                d.text((3,216),label,font=font,fill='white');d.text((3,237),str(Image.open(p).size),font=font,fill='white');tiles.append(tile)
            except Exception as e:print('TEX_ERROR',key,p.name,str(e))
        if tiles:
            canvas=Image.new('RGB',(220*6,255*((len(tiles)+5)//6)),'#222222')
            for i,tile in enumerate(tiles):canvas.paste(tile,(i%6*220,i//6*255))
            canvas.save(OUT/(key+'_textures.jpg'))
        print('TEXTURE_SHEET',key,len(tiles))
