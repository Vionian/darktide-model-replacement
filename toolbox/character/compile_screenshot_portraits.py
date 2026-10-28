"""Compile selected screenshot cutouts into native textures in model manifests.

Uses the existing v67 writer; does not rebuild any character unit or material.
The HUD's native portrait-frame material supplies masking, borders and status.
"""
from pathlib import Path
import hashlib
import importlib.util
import io
import json
import struct
import subprocess

from PIL import Image
from native_texture import Oodle, pack_texture
from read_native_texture import read_native_top_mip

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tools/model-work/distribution_fix/screenshot_portraits'
GAME = Path('<DARKTIDE_GAME>')
spec = importlib.util.spec_from_file_location('portrait_hash', ROOT / 'tools/bitsquid-addon/murmur/murmurhash64.py')
hash_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hash_module)
hash64 = hash_module.hash64


def main():
    codec = Oodle(GAME / 'binaries/oo2core_9_win64.dll')
    dds_dir = SOURCE / 'dds'
    dds_dir.mkdir(exist_ok=True)
    audit = []
    for source in json.loads((SOURCE / 'portrait_sources.json').read_text(encoding='utf-8')):
        key = source['asset']
        folder = ROOT / 'Custom' / key
        name = f'content/mods/{key}/{key}_portrait'
        stem = key + '_portrait'
        png = SOURCE / source['output']
        # Avoid dark fringes when mip filtering mixes transparent border pixels.
        # texconv's separate-alpha filter preserves the authored straight alpha.
        cmd = [str(ROOT / 'tools/texconv.exe'), '-nologo', '-y', '-dx10', '-srgbi',
               '-sepalpha', '-f', 'BC3_UNORM_SRGB', '-m', '0', '-o', str(dds_dir), str(png)]
        result = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        dds = (dds_dir / (key + '.dds')).read_bytes()
        stream = f'data/at/{hash64(name + "_stream"):016x}.stream'
        body, tail, high = pack_texture(dds, stream, codec, 0x6bd03744)
        primary = struct.pack('<QQIII', hash64('texture'), hash64(name), 1, 0, 0)
        primary += b'\x00' + struct.pack('<I', len(body)) + b'\x01' + struct.pack('<I', len(tail)) + body + tail
        texture = folder / (stem + '.texture')
        texture.write_bytes(primary)
        (folder / stream).write_bytes(high)
        readback, metadata = read_native_top_mip(texture, codec)
        assert readback[148:] == dds[148:148 + 512 * 512], key
        assert (metadata['width'], metadata['height'], metadata['dxgi']) == (512, 512, 78)
        (dds_dir / (key + '_readback.dds')).write_bytes(readback)
        # PIL decodes BC3 independently, including the actual alpha channel.
        # Pillow's legacy DXT5 decoder reads the identical BC3 blocks. Only the
        # preview copy loses its DX10 header; the game resource stays sRGB.
        preview_dds = bytearray(readback[:128] + readback[148:])
        preview_dds[84:88] = b'DXT5'
        decoded = Image.open(io.BytesIO(preview_dds)).convert('RGBA')
        decoded.save(SOURCE / (key + '_native_readback.png'))
        assert decoded.getchannel('A').getextrema() == (0, 255)
        path = folder / 'build.json'
        build = json.loads(path.read_text(encoding='utf-8'))
        resource = {'type': 'texture', 'name': name}
        build['artifacts'] = [a for a in build['artifacts'] if a.get('resource') != resource]
        for role, relative in [('primary', texture.name), ('stream', stream)]:
            build['artifacts'].append({'resource': resource, 'role': role, 'path': relative,
                                       'size': (folder / relative).stat().st_size})
        build['resources'] = list(dict.fromkeys([*build['resources'], texture.name, stream]))
        path.write_text(json.dumps(build, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        manifest = folder / 'compile_manifest.json'
        data = json.loads(manifest.read_text(encoding='utf-8'))
        data['screenshot_portrait'] = {'resource': name, 'source': source['source'],
                                      'crop_xyxy': source['crop_xyxy'], 'transparent': True,
                                      'sha256': hashlib.sha256(png.read_bytes()).hexdigest()}
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        audit.append({'asset': key, 'texture': name, **metadata, 'top_mip_matches_encoder': True,
                      'transparent_alpha_verified': True, 'source': source['source']})
        print('PORTRAIT_TEXTURE_OK', key, flush=True)
    (SOURCE / 'native_checks.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
