import argparse
import json
import pathlib
import struct
import ctypes


ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CUSTOM_ROOT = ROOT / "Custom"
DEFAULT_TEXTURES = (
    "qianxia/qianxia_material_0_bc.texture",
    "daniya_blue/daniya_blue_material_1_bca.texture",
)
COMMON_DDS_FOURCC = {b"DXT1", b"DXT3", b"DXT5", b"ATI1", b"ATI2", b"BC4U", b"BC5U", b"DX10"}


def unpack_u32(data, offset):
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"u32 field is outside the stream at offset {offset}")
    return struct.unpack_from("<I", data, offset)[0]


def parse_material_stream(data):
    material_offset = unpack_u32(data, 4)
    offset = material_offset + 4 + 16
    unknown_count = unpack_u32(data, offset)
    offset += 4 + unknown_count * 4
    texture_count = unpack_u32(data, offset)
    offset += 4
    textures = []
    for _ in range(texture_count):
        if offset + 12 > len(data):
            raise ValueError("Texture reference array extends past the material stream")
        channel_hash, resource_hash = struct.unpack_from("<IQ", data, offset)
        textures.append({
            "channel_hash": f"0x{channel_hash:08x}",
            "resource_hash": f"0x{resource_hash:016x}",
        })
        offset += 12
    return textures


def material_references(custom_root, texture_hash):
    references = []
    for primary in custom_root.rglob("*.material"):
        header = primary.read_bytes()
        if len(header) < 68:
            continue
        stream_name = header[38:68].split(b"\0", 1)[0].decode("ascii", errors="ignore")
        if not stream_name:
            continue
        stream_path = primary.parent.joinpath(*pathlib.PurePosixPath(stream_name).parts)
        if not stream_path.is_file():
            continue
        try:
            textures = parse_material_stream(stream_path.read_bytes())
        except (ValueError, struct.error):
            continue
        for texture in textures:
            if texture["resource_hash"] == f"0x{texture_hash:016x}":
                references.append({
                    "material": str(primary.relative_to(custom_root)).replace("\\", "/"),
                    "stream": str(stream_path.relative_to(custom_root)).replace("\\", "/"),
                    "stream_bytes": stream_path.stat().st_size,
                    **texture,
                })
    return references


def parse_texture(path, custom_root):
    data = path.read_bytes()
    if len(data) < 16:
        raise ValueError(f"Texture resource is shorter than its common header: {path}")
    type_hash, resource_hash = struct.unpack_from("<QQ", data, 0)
    body_size = unpack_u32(data, 29)
    mode = data[28]
    stream_name = None
    payload = data[38:38 + body_size]
    if mode == 1:
        stream_name = payload.split(b"\0", 1)[0].decode("ascii")
        payload = path.parent.joinpath(*pathlib.PurePosixPath(stream_name).parts).read_bytes()
    kind = unpack_u32(payload, 0)
    decoded_dds = None
    if kind == 0:
        decoded_dds = payload[12:]
    elif kind == 1:
        compressed_size, decoded_size = struct.unpack_from("<II", payload, 4)
        dll_path = pathlib.Path(r"<DARKTIDE_GAME>\binaries\oo2core_9_win64.dll")
        dll = ctypes.CDLL(str(dll_path))
        decode = dll.OodleLZ_Decompress
        decode.restype = ctypes.c_int64
        decode.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_int64,
                           ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int64,
                           ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int]
        source = ctypes.create_string_buffer(payload[12:12+compressed_size])
        output = ctypes.create_string_buffer(decoded_size)
        scratch = ctypes.create_string_buffer(0x100000)
        written = decode(source, compressed_size, output, decoded_size, 1, 0, 3, None, 0, None, None, scratch, len(scratch), 3)
        if written != decoded_size:
            raise ValueError("Oodle DDS decompression failed")
        decoded_dds = output.raw
    native = {"mode": mode, "kind": kind, "stream": stream_name}
    if decoded_dds is not None:
        if decoded_dds[:4] != b"DDS ":
            raise ValueError("Decoded native texture is not DDS")
        native.update({"dds_bytes": len(decoded_dds), "width": unpack_u32(decoded_dds, 16),
                       "height": unpack_u32(decoded_dds, 12), "mips": unpack_u32(decoded_dds, 28),
                       "fourcc": decoded_dds[84:88].decode("ascii"),
                       "dxgi_format": unpack_u32(decoded_dds, 128) if decoded_dds[84:88] == b"DX10" else None})
        if kind == 1:
            offset = 12 + compressed_size
            native["metadata_version"] = unpack_u32(payload, offset)
            native["largest_width"] = unpack_u32(payload, offset + 12)
            native["largest_height"] = unpack_u32(payload, offset + 16)
            # Inline texture wrappers store the external high mip path as a 31-byte tail.
            possible = data[-31:].split(b"\0", 1)[0]
            if possible.startswith(b"data/"):
                native["high_mip_stream"] = possible.decode("ascii")
                native["high_mip_stream_bytes"] = (path.parent / native["high_mip_stream"]).stat().st_size
    dds_offsets = []
    cursor = 0
    while True:
        cursor = data.find(b"DDS ", cursor)
        if cursor < 0:
            break
        dds_offsets.append(cursor)
        cursor += 4

    dds_reports = []
    for offset in dds_offsets:
        dds = {"offset": offset, "remaining_bytes": len(data) - offset}
        if offset + 128 <= len(data):
            size, flags, height, width, pitch, depth, mip_count = struct.unpack_from(
                "<7I", data, offset + 4
            )
            pixel_size, pixel_flags = struct.unpack_from("<2I", data, offset + 76)
            fourcc = data[offset + 84:offset + 88]
            valid = (
                size == 124 and pixel_size == 32 and 0 < width <= 32768
                and 0 < height <= 32768 and fourcc in COMMON_DDS_FOURCC
            )
            dds.update({
                "header_size": size,
                "flags": f"0x{flags:08x}",
                "width": width,
                "height": height,
                "pitch_or_linear_size": pitch,
                "depth": depth,
                "mip_count": mip_count,
                "pixel_format_size": pixel_size,
                "pixel_format_flags": f"0x{pixel_flags:08x}",
                "fourcc": fourcc.decode("ascii", errors="replace"),
                "standard_dds_header": valid,
                "pixel_data_offset_if_plain_dds": offset + 128,
            })
        else:
            dds["standard_dds_header"] = False
            dds["reason"] = "Truncated before a complete 128-byte DDS header"
        dds_reports.append(dds)

    primary_words = [
        f"0x{unpack_u32(data, offset):08x}"
        for offset in range(16, min(56, len(data) - 3), 4)
    ]
    return {
        "file": str(path.relative_to(custom_root)).replace("\\", "/"),
        "bytes": len(data),
        "type_hash": f"0x{type_hash:016x}",
        "resource_hash": f"0x{resource_hash:016x}",
        "version": unpack_u32(data, 16) if len(data) >= 20 else None,
        "native_decoded": native,
        "header_words_0x10_to_0x37": primary_words,
        "dds_markers": dds_reports,
        "material_references": material_references(custom_root, resource_hash),
    }


def main():
    parser = argparse.ArgumentParser(description="Inspect Darktide texture resources and material stream references")
    parser.add_argument("--custom-root", type=pathlib.Path, default=DEFAULT_CUSTOM_ROOT)
    parser.add_argument("textures", nargs="*", default=list(DEFAULT_TEXTURES))
    args = parser.parse_args()
    custom_root = args.custom_root.resolve()
    reports = []
    for relative in args.textures:
        path = (custom_root / relative).resolve()
        if not path.is_relative_to(custom_root) or not path.is_file():
            raise FileNotFoundError(f"Texture is missing or outside Custom root: {path}")
        reports.append(parse_texture(path, custom_root))
    print(json.dumps({"custom_root": str(custom_root), "textures": reports}, indent=2))


if __name__ == "__main__":
    main()
