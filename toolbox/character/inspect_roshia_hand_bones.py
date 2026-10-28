import bpy
bpy.ops.wm.open_mainfile(filepath=r'<SOURCE_ROOT>\Rossia\洛茜.blend')
arm=bpy.data.objects['洛茜_arm']
for suffix in ('.L','.R'):
    print('SIDE',suffix)
    for label in ('親指０','親指１','親指２','人指１','人指２','人指３','中指１','中指２','中指３','薬指１','薬指２','薬指３','小指１','小指２','小指３'):
        b=arm.data.bones.get(label+suffix)
        if b:
            v=b.tail_local-b.head_local
            print(label, round(v.length,5), 'head', tuple(round(x,4) for x in b.head_local), 'parent', b.parent.name if b.parent else None)
