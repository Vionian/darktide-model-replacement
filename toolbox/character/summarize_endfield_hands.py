import pathlib,json
from PIL import Image,ImageDraw,ImageFont,ImageChops
HERE=pathlib.Path(__file__).parent/'endfield_batch'
MODELS={'lizhiyan':'李织烟','endministrator_f':'女管理员','si':'祀','typhoea':'提弗洛斯'}
font=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',21)
def subject(path):
    im=Image.open(path).convert('RGB')
    bg=Image.new('RGB',im.size,im.getpixel((0,0)))
    mask=ImageChops.difference(im,bg).convert('L').point(lambda v:255 if v>8 else 0)
    box=mask.getbbox()
    return im.crop(box) if box else im
def make(filename,columns):
    width=400*len(columns)
    canvas=Image.new('RGB',(width,4*350+50),'#20262e');draw=ImageDraw.Draw(canvas)
    for col,(_,_,title) in enumerate(columns):draw.text((col*400+12,8),title,font=font,fill='white')
    for row,(key,label) in enumerate(MODELS.items()):
        for col,(folder,side,_) in enumerate(columns):
            path=next((HERE/key/folder).glob('*_'+side+'_front_preview.png'))
            im=subject(path);im.thumbnail((380,300))
            x=col*400+(400-im.width)//2;y=row*350+90
            canvas.paste(im,(x,y))
            draw.text((col*400+12,row*350+54),label,font=font,fill='white')
    canvas.save(HERE/filename)
make('hand_mmr_before_after.png',[
    ('preview_rest_hands','left','之前 · 左手'),('hand_mmr_rest','left','MMR 优化后 · 左手'),
    ('preview_rest_hands','right','之前 · 右手'),('hand_mmr_rest','right','MMR 优化后 · 右手')])
make('hand_mmr_motion_overview.png',[
    ('hand_mmr_staff','left','合成法杖动作 · 左手'),('hand_mmr_staff','right','合成法杖动作 · 右手')])
audit=json.loads((HERE/'hand_optimization_audit.json').read_text(encoding='utf-8'))
text='''# 四模型手部 MMR 优化记录

处理对象：李织烟、女管理员、祀、提弗洛斯。沿用洛茜已经采用的暗潮原生手部动画连接方式。

- 保留各自原模型的手部网格、UV、贴图和源蒙皮权重。
- 实际在各自原始 MMD 骨架上使用 MMR BoneAnimCopy：2 根手腕与 30 根手指，关闭 90 度自动取整。读取插件求值后的关节位置和旋转，烘入离线手部拟合矩阵。
- 对照达妮娅、千咲、爱弥斯的手部截面，按每根手指统一截面缩放，取消各指节独立横向偏移；指节方向和掌指衔接按各自原模处理。
- 最终游戏资源继续使用暗潮原生手腕/手指节点、层级和逆绑定；不加入逐帧手指重写或每武器猜测偏移。
- 第三人称资源与上一版逐文件 SHA256 一致。本轮优化集中在第一人称手部表面，不改变已接受的身体骨架。

## 检查范围

每个角色的 `*_original_hand_MMR.blend` 保留原模型与真实 MMR 约束；`mmr_hand_authoring.json` 包含 32 根骨骼的转换数据与 7 组原模型动作探针。源文件没有原游戏动作，这些姿势是合成测试，不是《终末地》动作捕捉。

另完成序列化资源回读、原生手部绑定/逆绑定不变检查、UV/权重不变检查、生产 Lua 22 组合成动作 × 20 帧，以及编译网格与预览重建流的一致性检查。

预览：`hand_mmr_before_after.png` 为左右手静止姿态前后对照；`hand_mmr_motion_overview.png` 为合成法杖动作。尚未启动游戏验证，不代表所有真实武器握持已通过。

部署状态与回滚备份：查看 `deployment_latest.json`。
'''
(HERE/'README_手部MMR优化.md').write_text(text,encoding='utf-8')
print('ENDFIELD_HAND_PREVIEWS_READY',list(audit))
