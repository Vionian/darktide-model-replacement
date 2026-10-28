"""Source identities for the user-supplied October 23 costume set."""
from pathlib import Path
HERE=Path(__file__).parent
OUT=HERE/'skins_20261023'
ROOT=Path('<SOURCE_ROOT>/Skins')
SOURCES={
 'endministrator_penguin':('企鹅-管理员','endministrator_f','mod.ini'),
 'roshia_cocoa_puff':('可可泡芙-洛茜','roshia','Rossi Cocoa Pufflet sfw v3.5 fix/Rossi SFW.ini'),
 'endministrator_devil':('小恶魔-管理员','endministrator_f','Endministrator(F).ini'),
 'mifu_commander':('总司-弭弗','mifu','Mi Fu Lord Commander full ver 4.6/MI FU.ini'),
 'si_ink_wash':('水墨-祀','si','mod.ini'),
 'gilberta_swimsuit':('泳装-洁尔佩塔','gilberta','mod.ini'),
 'saixi_swimsuit':('泳装-赛希','saixi','mod.ini'),
 'roshia_lolita':('洛丽塔-洛茜','roshia','洛茜.ini'),
 'aitela_hiro':('筱泽广-埃特拉','aitela','筱泽广_埃特拉.ini'),
 'laiwanting_simple':('简化-莱万汀','laiwanting','mod.ini'),
 'chenqianyu_sport':('运动服-陈千语','chenqianyu','mod.ini'),
}

def source(key):
    title,base,ini=SOURCES[key]
    file=ROOT/title/ini
    return dict(key=key,title=title.split('-')[0],folder=ROOT/title,base=base,ini=file)
