-- Only list weapons whose model and attachment path are supported.
return {classes={
    {id='veteran', title='class_veteran', weapons={}},
    {id='zealot', title='class_zealot', weapons={{id='relicsword_2h',title='weapon_relicsword_2h',setting='skin_zealot_relicsword_2h',default='none',skins={{id='none',title='skin_none'},{id='khravengger',title='skin_khravengger'}}}}},
    {id='psyker', title='class_psyker', weapons={
        {id='forcesword_1h', title='weapon_forcesword_1h', setting='skin_psyker_forcesword_1h',
         default='langzhifei', skins={{id='none',title='skin_none'},{id='langzhifei',title='skin_langzhifei'}}},
        {id='forcesword_2h', title='weapon_forcesword_2h', setting='skin_psyker_forcesword_2h',
         default='khravengger', skins={{id='none',title='skin_none'},{id='khravengger',title='skin_khravengger'}}},
    }},
    {id='adamant', title='class_adamant', weapons={}},
    {id='broker', title='class_broker', weapons={}},
    {id='cryptic', title='class_cryptic', weapons={}},
}}
