from pathlib import Path
import json
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/force_sword_pose'
measure=json.loads((OUT/'langzhifei_alignment.json').read_text())
font_path='<WINDOWS_FONTS>/msyh.ttc'
font=lambda size:ImageFont.truetype(font_path,size)
image=Image.new('RGB',(1740,1080),'#121b26');draw=ImageDraw.Draw(image)
draw.text((35,18),'狼之绯 · 普通单手力场剑握点校准',font=font(29),fill='#e8edf2')
draw.text((35,63),'静态资源坐标对照：绿色虚线 = 原生握柄中心；金色线 = 武器根节点 Z=0',font=font(18),fill='#b9c7d4')
native=np.load(OUT/'native_assembled.npz')
old=np.load(OUT/'old_mesh.npz');new=np.load(OUT/'compiled_mesh.npz')
models=[[(native[k],native[k+'_faces']) for k in ('grip','hilt','blade','pommel')],
    [(old['vertices'],old['faces'])],[(new['vertices'],new['faces'])]]
titles=['原生单手力场剑','旧版狼之绯','修正版狼之绯']
colors=[np.array([154,170,190]),np.array([196,111,111]),np.array([101,192,212])]
grip_z=measure['target_grip_center'][2]
for row in range(2):
    for col in range(3):
        x0=20+col*575;y0=112+row*455;w=555;h=435
        draw.rounded_rectangle((x0,y0,x0+w,y0+h),radius=12,fill='#1b2734')
        draw.text((x0+16,y0+12),titles[col]+(' / 握柄近景' if row else ''),font=font(21),fill='#e5edf5')
        scale=242 if row==0 else 1200
        zcenter=.42 if row==0 else -.05
        xc=x0+w*.5;yc=y0+235
        def proj(p):return (xc+p[1]*scale,yc-(p[2]-zcenter)*scale)
        for z,color in [(0,'#bd9656'),(grip_z,'#70d49c')]:
            y=proj((0,0,z))[1]
            for x in range(x0+10,x0+w-10,15):draw.line((x,y,min(x+8,x0+w-10),y),fill=color,width=2)
        tris=[]
        for v,f in models[col]:
            p=v[f];normal=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])
            for triangle,n in zip(p,normal):
                if n[0]>=0:continue
                intensity=.4+.6*max(0,float(np.dot(n/np.linalg.norm(n),[-.82,-.25,.52])))
                shade=tuple((colors[col]*intensity).clip(0,255).astype(int))
                tris.append((float(triangle[:,0].mean()),triangle,shade))
        layer=Image.new('RGBA',(w-20,h-100),(0,0,0,0))
        layer_draw=ImageDraw.Draw(layer)
        for _,triangle,color in sorted(tris,key=lambda item:item[0],reverse=True):
            points=[(proj(p)[0]-x0-10,proj(p)[1]-y0-52) for p in triangle]
            layer_draw.polygon(points,fill=tuple(color)+(255,))
        image.paste(layer,(x0+10,y0+52),layer)
        center=measure['old_grip_center'] if col==1 else measure['target_grip_center']
        if row:
            cx,cy=proj(center);draw.ellipse((cx-6,cy-6,cx+6,cy+6),outline='#f3f8ff',width=2)
            draw.text((x0+14,y0+h-36),'握柄中心 Z = '+f'{center[2]:+.3f} m',font=font(17),fill='#d5e2ec')
draw.text((35,1037),'只校准武器外观：手部骨骼、待机／格挡／攻击动画保持游戏原生。游戏内接触效果仍需实测。',font=font(18),fill='#bdcad6')
image.save(OUT/'alignment_comparison.png')
print(OUT/'alignment_comparison.png')
