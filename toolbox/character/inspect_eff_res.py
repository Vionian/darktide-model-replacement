from pathlib import Path
import struct,json
root=Path('<SOURCE_ROOT>/Skins/水墨-祀')
for ext in ('mesh','tex','mat'):
    f=next(root.rglob('*.'+ext));b=f.read_bytes()
    print('EFF',ext,f.name,len(b),struct.unpack_from('<4I',b,8))
    offset=80;entries=[]
    for _ in range(struct.unpack_from('<I',b,16)[0]):
        n=struct.unpack_from('<H',b,offset)[0];offset+=2
        label=b[offset:offset+n].decode();offset+=n
        start,size=struct.unpack_from('<QQ',b,offset);offset+=48
        entries.append(dict(name=label,start=start,size=size,head=b[start:start+min(size,80)].hex()))
    print(json.dumps(entries,indent=2))
