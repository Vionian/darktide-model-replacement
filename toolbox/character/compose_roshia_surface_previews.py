"""Arrange actual Blender renders; no content retouching."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent / 'roshia/surface_uv_candidate'
FONT = '<WINDOWS_FONTS>/msyh.ttc'
def font(size):
    return ImageFont.truetype(FONT, size)
def render_file(folder, suffix):
    files = list((ROOT / folder).glob('*' + suffix + '_preview.png'))
    if len(files) != 1:
        raise ValueError((folder, suffix, files))
    return files[0]
def sheet(name, title, panels, columns, cell=(600, 820), footer='离线 Blender 预览；最终 .unit + 原生 .texture 回读；不代表游戏实际光照或动画。'):
    rows = (len(panels) + columns - 1) // columns
    w, h = columns * cell[0], 92 + rows * (cell[1] + 50) + 62
    out = Image.new('RGB', (w, h), '#20242b')
    d = ImageDraw.Draw(out)
    d.text((28, 24), title, font=font(32), fill='#f5f6f8')
    for i, (label, path, crop) in enumerate(panels):
        im = Image.open(path).convert('RGB')
        if crop:
            im = im.crop(crop)
        im = ImageOps.contain(im, cell, Image.Resampling.LANCZOS)
        x = (i % columns) * cell[0]
        y = 92 + (i // columns) * (cell[1] + 50)
        d.text((x + 24, y + 8), label, font=font(25), fill='#e0e7ef')
        out.paste(im, (x + (cell[0] - im.width) // 2, y + 50 + (cell[1] - im.height) // 2))
    d.text((28, h - 43), footer, font=font(20), fill='#b9c6d4')
    out.save(ROOT / name)
    print(ROOT / name)

body_crop = (210, 175, 1000, 1235)
sheet('body_views.png', '洛茜｜修正后的全身三视图', [
    (label, render_file('final_body_preview', side), body_crop)
    for label, side in [('正面', 'front'), ('侧面', 'side'), ('背面', 'back')]
], 3)
sheet('detail_views.png', '洛茜｜面部、肩部与尾巴细节', [
    ('面部与肩部', render_file('detail_upper', 'front'), (230, 270, 970, 1010)),
    ('肩部侧面', render_file('detail_upper', 'side'), (230, 270, 970, 1010)),
    ('尾巴与披风', render_file('detail_tail', 'back'), (200, 400, 1000, 1200)),
], 3, (600, 630))
sheet('uv_comparison.png', '洛茜｜同一网格、同一光照下的 UV 修复对照', [
    ('修复前：旧 V 原点复现', render_file('final_wrong_uv_preview', 'front'), (280, 220, 920, 830)),
    ('修复后：V = 1 − V', render_file('final_body_preview', 'front'), (280, 220, 920, 830)),
], 2, (800, 760))
sheet('hand_views.png', '洛茜｜第一人称双手与人工握拳检查', [
    ('1P 双臂参考姿态', render_file('final_arms_preview', 'front'), (80, 430, 1120, 950)),
    ('1P 双臂侧面', render_file('final_arms_preview', 'side'), (80, 430, 1120, 950)),
    ('左手：人工握拳', render_file('final_hand_preview', 'left_front'), (0, 430, 1100, 980)),
    ('右手：人工握拳', render_file('final_hand_preview', 'right_back'), (0, 430, 1100, 980)),
], 2, (800, 430), '握拳为合成压力姿态，不是实机武器动作；上臂截口仍沿三角面边界。')
