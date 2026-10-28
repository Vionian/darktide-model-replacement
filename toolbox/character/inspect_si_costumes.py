"""Inventory local EFMI packages without executing INI commands."""
import re,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parent
PACKAGES={'si_short_skirt':('短裙-祀','祀.ini'),'si_lolita':('洛丽塔-祀','si.ini')}
def read_sections(path):
    txt=path.read_text(encoding='utf-8-sig')
    parts=re.split(r'^\[([^\]]+)\]\s*$',txt,flags=re.M)
    return dict(zip(parts[1::2],parts[2::2]))
if __name__=='__main__':
    out=ROOT/'si_costumes';out.mkdir(exist_ok=True)
    reports={}
    for key,(dirname,filename)in PACKAGES.items():
        folder=pathlib.Path('<SOURCE_ROOT>')/dirname
        blocks=read_sections(folder/filename)
        resources={name:dict(re.findall(r'^\s*([\w.-]+)\s*=\s*(.+?)\s*$',txt,re.M))for name,txt in blocks.items()if name.startswith('Resource')}
        draw_sections={name:txt for name,txt in blocks.items()if re.search(r'(?m)^\s*drawindexed\s*=',txt)}
        relevant={name:txt for name,txt in blocks.items()if re.search(r'(?mi)^\s*(ps-t|vb[012]|ib|handling|drawindexed|filename|stride|format|author|name|description|mod_author)',txt)}
        reports[key]={'source':str(folder),'resources':resources,'draw_sections':draw_sections,'relevant_sections':relevant}
        for name,txt in draw_sections.items():print(key,name,txt[:2200])
    (out/'source_inventory.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
