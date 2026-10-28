"""Read serialized UNIT material IDs, not just build-manifest dependency lists.

Uses the downloaded GPL-3.0 SDK reader. This reader intentionally rejects
unsupported physical/terrain records rather than declaring an unchecked model valid.
"""
import json
from pathlib import Path
import struct

from darktide import inside, murmur64


def material_bindings(blob, sdk):
    nodes, reader = sdk.reference_skeleton._read_unit(blob)
    for _ in range(2):
        if reader.u32():
            raise ValueError('Native material audit expects cosmetic units without physics actors')
    reader.u32_array()
    reader.take(reader.u32() * 32)
    reader.take(reader.u32() * 160)
    reader.array()
    for _ in range(reader.u32()):
        reader.take(16)
        for _ in range(reader.u32()):
            reader.take(8)
            reader.u32_array()
            reader.take(8)
        reader.take(48)
        reader.u32_array()
        reader.take(5)
    if reader.u32() or reader.u32() or reader.u32() or reader.u32() or reader.u32():
        raise ValueError('Unsupported terrain/joint/mover records in a cosmetic unit')
    reader.take(1)
    reader.array()
    reader.array()
    for _ in range(reader.u32()):
        reader.take(4)
        reader.u32_array()
    for _ in range(4):
        reader.array()
    reader.take(8)
    bindings = [struct.unpack('<IQ', reader.take(12)) for _ in range(reader.u32())]
    if not bindings or any(resource == 0 for _, resource in bindings):
        raise ValueError('UNIT has missing or zero native material resource bindings')
    if len(dict(bindings)) != len(bindings):
        raise ValueError('UNIT contains duplicate material slots')
    return nodes, bindings


def audit_asset(folder, sdk):
    folder = Path(folder)
    manifest = json.loads((folder / 'build.json').read_text(encoding='utf-8-sig'))
    resources = manifest['resources']
    materials = {murmur64(r['key']['name']): r for r in resources if r['key']['type'] == 'material'}
    audits = []
    for entry in resources:
        if entry['key']['type'] != 'unit':
            continue
        unit = inside(folder, entry['file']['path'])
        blob = unit.read_bytes()
        expected = (murmur64('unit'), murmur64(entry['key']['name']))
        if struct.unpack_from('<QQ', blob) != expected:
            raise ValueError('UNIT cooked header does not match manifest resource identity')
        nodes, bindings = material_bindings(blob, sdk)
        for _, identity in bindings:
            if identity not in materials:
                raise ValueError(f'UNIT material {identity:016x} is absent from the local package')
        audits.append({'unit': entry['key']['name'], 'nodes': len(nodes), 'material_bindings': len(bindings),
                       'zero_material_ids': 0, 'all_bound_materials_in_manifest': True})
    if not audits:
        raise ValueError('No native UNIT was audited')
    return {'asset': folder.name, 'units': audits, 'in_game_visual_verified': False}
