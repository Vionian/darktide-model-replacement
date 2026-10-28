"""User-selected source screenshots: crop + alpha only, no face repaint."""
from pathlib import Path
import hashlib
import json
import shutil
import build_screenshot_portraits as portraits

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'tools/model-work/endfield_batch/wave3_portraits'
SOURCE = OUT / 'source'
SOURCES = {
    'laiwanting': Path('<SCREENSHOT_ROOT>/source.png'),
    'aitela': Path('<SCREENSHOT_ROOT>/source.png'),
    'saixi': Path('<SCREENSHOT_ROOT>/source.png'),
}

def main():
    SOURCE.mkdir(parents=True, exist_ok=True)
    for key, source in SOURCES.items():
        target = SOURCE / (key + '.png')
        if source.exists():
            shutil.copy2(source, target)
        elif not target.exists():
            raise FileNotFoundError(source)
    portraits.SOURCE = SOURCE
    portraits.OUT = OUT
    portraits.SPECS = [
        ('aitela', '埃特拉', 'aitela.png', (126, 12, 446, 374)),
        ('laiwanting', '莱万汀', 'laiwanting.png', (292, 10, 590, 354)),
        ('saixi', '赛希', 'saixi.png', (48, 0, 424, 487)),
    ]
    # Source-pixel seeds retain white ear interiors and slender horn tips.
    # Coordinates are local to the crop; only the alpha mask changes.
    portraits.FOREGROUND_SEEDS = {
        'aitela': [
            [(130, 63), (146, 38), (158, 39), (173, 48), (198, 70), (184, 81)],
            [(277, 83), (293, 85), (300, 93), (301, 121), (287, 119)],
        ],
        'laiwanting': [
            [(47, 73), (56, 48), (72, 30), (90, 21), (75, 40), (65, 62), (65, 91)],
            [(164, 18), (183, 28), (201, 49), (214, 70), (215, 102), (198, 95), (196, 62), (184, 39)],
        ],
        'saixi': [
            [(139, 10), (145, 13), (140, 47), (130, 81), (120, 101), (113, 126), (93, 136), (85, 112), (105, 98), (124, 63)],
            [(234, 12), (241, 43), (252, 71), (264, 95), (279, 101), (282, 132), (264, 150), (252, 124), (240, 89), (235, 56)],
            [(163, 403), (214, 403), (213, 440), (235, 463), (241, 486), (141, 486), (147, 459), (166, 439)],
            [(80, 289), (90, 331), (96, 381), (111, 425), (91, 454), (63, 479), (47, 484), (59, 445), (67, 402), (68, 352), (72, 305)],
            [(300, 290), (307, 334), (315, 380), (320, 420), (333, 474), (319, 483), (304, 445), (294, 400), (296, 350)],
        ],
    }
    portraits.crop_previews()
    portraits.matte_portraits()
    from PIL import Image
    contact = OUT / 'portrait_contact.jpg'
    with Image.open(contact) as sheet:
        sheet.crop((0, 0, 1200, 480)).save(contact, quality=95)
    path = OUT / 'portrait_sources.json'
    records = json.loads(path.read_text(encoding='utf-8'))
    for record in records:
        record['user_supplied_source'] = str(SOURCES[record['asset']])
        record['source_sha256'] = hashlib.sha256(Path(record['source']).read_bytes()).hexdigest()
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

if __name__ == '__main__':
    main()
