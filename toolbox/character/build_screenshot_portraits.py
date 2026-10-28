"""Crop and matte explicitly selected reference screenshots without redrawing faces."""
from pathlib import Path
import json

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT.parent / "终末地"
OUT = ROOT / "tools/model-work/distribution_fix/screenshot_portraits"
SPECS = [
    ("chenqianyu", "陈千语", "09146be9-3fdf-4d81-98c4-61e61b3cf158.png", (175, 0, 505, 350)),
    ("liino", "梨诺", "1eb534f0-a7bd-45b4-8b35-4c5a6aee7907.png", (220, 6, 595, 400)),
    ("mifu", "弭弗", "5f2036d0-e94f-48c6-925f-55823d6dc071.png", (205, 0, 625, 380)),
    ("perlica", "佩丽卡", "7affb7c8-c508-4aee-8abe-06dc90e68d54.png", (175, 25, 545, 390)),
    ("tangtang", "汤汤", "7c0e0698-4385-475e-8d12-a682cf8633c1.png", (200, 0, 490, 360)),
    ("gilberta", "洁尔佩塔", "790f91c9-379e-4e47-a480-0a8751724bf8.png", (200, 10, 735, 480)),
    ("yvonne", "伊冯", "ebe0fdb3-de22-4191-ae2c-3ecec1b3a283.png", (350, 0, 875, 490)),
    ("zhuangfangyi", "庄方宜", "d9773aca-8256-4793-8f01-39a5d8b224bc.png", (265, 0, 595, 360)),
    ("roshia", "洛茜", "../实机演示/Screenshot_2026-10-17-16-38-15-476_com.hypergryph.jpg", (235, 95, 490, 425)),
]

# Segmentation can mistake gray/white ear interiors for the gray stage. These
# source-pixel seeds recover those authored parts; they do not invent pixels.
FOREGROUND_SEEDS = {
    "roshia": [
        [(44, 30), (80, 104), (43, 123)],
        [(144, 20), (166, 107), (114, 102)],
        [(81, 132), (162, 130), (183, 190), (184, 266), (204, 315),
         (185, 329), (55, 329), (77, 281), (63, 223), (58, 177)],
    ],
    "chenqianyu": [
        [(44, 0), (53, 26), (69, 45), (98, 61), (78, 58), (81, 80),
         (107, 94), (101, 109), (80, 98), (75, 81), (66, 57), (53, 39)],
        [(241, 0), (248, 0), (246, 18), (251, 34), (245, 51), (250, 63),
         (244, 78), (248, 99), (238, 103), (236, 80), (239, 64),
         (235, 49), (229, 50), (235, 29)],
    ],
}


def infer(session, im):
    a = np.asarray(im.resize((320, 320), Image.Resampling.LANCZOS), dtype=np.float32) / 255
    a = ((a - np.array([.485, .456, .406])) / np.array([.229, .224, .225])).astype(np.float32)
    mask = session.run(None, {session.get_inputs()[0].name: a.transpose(2, 0, 1)[None]})[0][0, 0]
    mask = (mask - mask.min()) / max(float(mask.max() - mask.min()), 1e-6)
    return cv2.resize(mask, im.size, interpolation=cv2.INTER_CUBIC).clip(0, 1)


def matte_portraits():
    session = ort.InferenceSession(str(ROOT / "tools/model-work/image_tools/u2netp.onnx"),
                                 providers=["CPUExecutionProvider"])
    audit = []
    sheet = Image.new("RGB", (1200, 1440), (36, 39, 44))
    font = ImageFont.truetype("<WINDOWS_FONTS>/msyh.ttc", 24)
    for i, (key, label, filename, box) in enumerate(SPECS):
        source = Image.open(SOURCE / filename).convert("RGB")
        im = source.crop(box)
        probability = infer(session, im)
        rgb = np.asarray(im)
        mask = np.full(probability.shape, cv2.GC_PR_BGD, dtype=np.uint8)
        mask[probability > .45] = cv2.GC_PR_FGD
        mask[probability < .025] = cv2.GC_BGD
        sure_fg = cv2.erode((probability > .9).astype(np.uint8), np.ones((3, 3), np.uint8)) != 0
        mask[sure_fg] = cv2.GC_FGD
        for polygon in FOREGROUND_SEEDS.get(key, []):
            seed = np.zeros(mask.shape, dtype=np.uint8)
            cv2.fillPoly(seed, [np.array(polygon, dtype=np.int32)], 1)
            mask[cv2.dilate(seed, np.ones((5, 5), np.uint8)) != 0] = cv2.GC_PR_FGD
            mask[seed != 0] = cv2.GC_FGD
        cv2.setRNGSeed(1)
        cv2.grabCut(rgb, mask, None, np.zeros((1, 65)), np.zeros((1, 65)), 6, cv2.GC_INIT_WITH_MASK)
        binary = np.isin(mask, [cv2.GC_FGD, cv2.GC_PR_FGD]).astype(np.uint8)
        # Retain the selected character, not separate UI or floating props.
        count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
        if count > 1:
            dominant = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            keep = stats[:, cv2.CC_STAT_AREA] >= stats[dominant, cv2.CC_STAT_AREA] * .005
            keep[0] = False
            binary = keep[labels].astype(np.uint8)
        alpha = cv2.GaussianBlur(binary.astype(np.float32), (0, 0), .65)
        alpha = np.clip(alpha * 255, 0, 255).astype(np.uint8)
        rgba = np.dstack((rgb, alpha))
        rgba[alpha == 0, :3] = 0
        cut = Image.fromarray(rgba, "RGBA")
        cut.save(OUT / f"{key}_cutout.png")
        # Keep the entire head/ear/horn silhouette inside a slightly padded HUD tile.
        scale = min(460 / cut.width, 476 / cut.height)
        cut = cut.resize((round(cut.width * scale), round(cut.height * scale)), Image.Resampling.LANCZOS)
        tile = Image.new("RGBA", (512, 512))
        tile.alpha_composite(cut, ((512 - cut.width) // 2, 18))
        tile.save(OUT / f"{key}.png")
        x, y = i % 3 * 400, i // 3 * 480
        preview = tile.resize((400, 400), Image.Resampling.LANCZOS)
        sheet.paste(preview, (x, y + 48), preview)
        ImageDraw.Draw(sheet).text((x + 12, y + 10), label, font=font, fill="white")
        audit.append({"asset": key, "label": label, "source": str((SOURCE / filename).resolve()),
                      "crop_xyxy": box, "output": f"{key}.png", "size": [512, 512],
                      "method": "U2NetP segmentation and GrabCut alpha only; original RGB preserved"})
        print("PORTRAIT", key, flush=True)
    sheet.save(OUT / "portrait_contact.jpg", quality=95)
    (OUT / "portrait_sources.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")


def crop_previews():
    OUT.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGB", (1200, 1320), (36, 39, 44))
    font = ImageFont.truetype("<WINDOWS_FONTS>/msyh.ttc", 20)
    for i, (key, label, filename, box) in enumerate(SPECS):
        im = Image.open(SOURCE / filename).convert("RGB").crop(box)
        im.save(OUT / f"{key}_crop.jpg")
        preview = im.copy()
        preview.thumbnail((390, 390))
        x, y = i % 3 * 400, i // 3 * 440
        sheet.paste(preview, (x, y + 28))
        ImageDraw.Draw(sheet).text((x + 6, y), f"{label} {im.width}x{im.height}", font=font, fill="white")
    sheet.save(OUT / "crop_contact.jpg", quality=95)


if __name__ == "__main__":
    crop_previews()
    matte_portraits()
