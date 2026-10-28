"""Third Endfield batch: explicit source identities, independent candidates."""
from pathlib import Path

SOURCE_ROOT = Path('<SOURCE_ROOT>')
BLEND_ROOT = SOURCE_ROOT / 'Darktide mod/Rossia'
PROFILES = {
    'aitela': {'name': '埃特拉', 'provider': 'AitelaReplacement',
               'hair': ('hair',), 'cloth': ('cloth', 'tail_', 'bag', 'collar_'),
               'source_dir': SOURCE_ROOT / '【明日方舟：终末地】埃特拉_by_茶叶味香皂_bd11f97809313641720cac0f604249c8'},
    'laiwanting': {'name': '莱万汀', 'provider': 'LaiwantingReplacement',
                  'hair': ('hair',), 'cloth': ('スカート', 'spring_', 'clothes_', 'bone_chain'),
                  'opaque_materials': (14,),
                  'source_dir': SOURCE_ROOT / '【明日方舟：终末地】莱万汀_by_茶叶味香皂_3f6b9d46454f2f5fcdcd2a1880e47a45'},
    'saixi': {'name': '赛希', 'provider': 'SaixiReplacement',
              'hair': ('hair_base_',),
              'cloth': ('dress_', 'tail_', 'streamer_', 'scarf_', 'hairscarf_', 'yidai_', 'pendant_', 'ball_'),
              'albedo_materials': ('丝袜(Cloth1)',),
              'source_dir': SOURCE_ROOT / '【明日方舟：终末地】赛希_by_茶叶味香皂_d4b31bbf47662e3bd5fb14a7d128fbfa'},
}
