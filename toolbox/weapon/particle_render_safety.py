"""Exclude the particle materials identified by the 2026-10-27 DX12 crash."""
import re

BAD_SHADER = 'c0aadc88'
BAD_MATERIAL_SOURCES = frozenset(('3cc662f0f916f54d','16fb6ccbceebfa9a','6b8aeb12d74faa27'))

def blocked_material(value):
    text=str(value).lower()
    return any(text=='#'+token or re.search(r'(?:^|/)fx_'+token+r'_',text)
               for token in BAD_MATERIAL_SOURCES)

def sanitize(effect):
    """Keep system indices, emitters, variables and every compatible draw intact."""
    removed=[]
    for system in effect.get('systems',[]):
        keep=[]
        for draw in system.get('visualizers',[]):
            if blocked_material(draw.get('material','')):
                removed.append({'system':system['name'],'material':draw['material'],'type':draw['type']})
            else:keep.append(draw)
        system['visualizers']=keep
    return removed
