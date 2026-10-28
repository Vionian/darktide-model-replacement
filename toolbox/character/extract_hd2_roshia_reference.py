"""Read-only HD2 StreamToc extraction; layout cross-checked against io_scene_helldivers2.
The supplied mod archive is never modified. Resource hashes remain the filenames.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

TYPES = {0xe0a48d0be9a7453f: 'unit', 0xcd4238c6a0c69e32: 'texture', 0xeac0b497876adedf: 'material'}

def extract(source, output):
    primary = source.read_bytes()
    gpu = Path(str(source) + '.gpu_resources').read_bytes()
    stream_path = Path(str(source) + '.stream')
    stream = stream_path.read_bytes() if stream_path.exists() else b''
    magic, type_count, count, _ = struct.unpack_from('<4I', primary)
    assert magic == 0xf0000011
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for i in range(count):
        v = struct.unpack_from('<7Q6I', primary, 72 + type_count*32 + i*80)
        key, kind, po, so, go, _, _, ps, ss, gs, _, _, _ = v
        extension = TYPES.get(kind, f'{kind:016x}')
        name = f'{key:016x}.{extension}'
        record = {'name':name, 'id':key, 'type':extension, 'parts':{}}
        parts = {}
        for label, data, start, size in [('primary',primary,po,ps),('gpu',gpu,go,gs),('stream',stream,so,ss)]:
            if not size: continue
            if start + size > len(data): raise ValueError(f'{name}: invalid {label} bounds')
            payload = data[start:start+size]
            filename = name + ('' if label == 'primary' else '.' + label)
            (output / filename).write_bytes(payload)
            record['parts'][label] = {'file':filename,'offset':start,'size':size,'sha256':hashlib.sha256(payload).hexdigest()}
            parts[label] = payload
        if extension == 'texture':
            header = parts['primary'][192:340]
            if header[:4] != b'DDS ': raise ValueError(f'{name}: DDS header missing')
            dds = header + parts.get('stream',parts.get('gpu',b''))
            (output / (name + '.dds')).write_bytes(dds)
            record['texture'] = {'width':struct.unpack_from('<I',header,16)[0], 'height':struct.unpack_from('<I',header,12)[0], 'mips':struct.unpack_from('<I',header,28)[0], 'dxgi':struct.unpack_from('<I',header,128)[0]}
        if extension == 'material':
            p = parts['primary']; n = struct.unpack_from('<I',p,64)[0]
            record['texture_slots'] = list(struct.unpack_from('<'+'I'*n,p,136))
            record['textures'] = [f'{x:016x}' for x in struct.unpack_from('<'+'Q'*n,p,136+4*n)]
        records.append(record)
    result = {'source':str(source),'source_sha256':hashlib.sha256(primary).hexdigest(),'entry_count':count,'entries':records}
    (output/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'extracted':count,'types':{t:sum(x['type']==t for x in records) for t in TYPES.values()},'output':str(output)},ensure_ascii=False))

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();extract(a.source,a.output)
