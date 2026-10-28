"""Read native v67 resources for previews, independently of pack_texture.

Largest-mip row assembly follows tools/limn-source/src/file/texture.rs.
Only the Oodle codec is shared with the writer; offsets, sizes and stream
paths are read back from the emitted resource rather than cached build data.
"""
import pathlib
import struct
from native_texture import Oodle


def read_native_top_mip(path, oodle):
    path = pathlib.Path(path)
    raw = path.read_bytes()
    if len(raw) < 38 or raw[28] != 0:
        raise ValueError(f"Expected inline native resource: {path}")
    body_size = struct.unpack_from("<I", raw, 29)[0]
    tail_size = struct.unpack_from("<I", raw, 34)[0]
    if len(raw) != 38 + body_size + tail_size:
        raise ValueError("Native wrapper length mismatch")
    body = raw[38:38 + body_size]
    kind, packed_size, decoded_size = struct.unpack_from("<III", body)
    if kind != 1:
        raise ValueError("Only Oodle v67 textures are supported")
    low_dds = oodle.decompress(body[12:12 + packed_size], decoded_size)
    if low_dds[:4] != b"DDS " or low_dds[84:88] != b"DX10":
        raise ValueError("Invalid embedded DX10 DDS")
    meta = 12 + packed_size
    version, flags, streamed_mips, width, height = struct.unpack_from("<5I", body, meta)
    if version != 67:
        raise ValueError(f"Unexpected texture metadata version {version}")
    meta_size, count, zero, count16 = struct.unpack_from("<IIHH", body, meta + 148)
    if meta_size != 8 + count * 4 or zero or count16 != count:
        raise ValueError("Invalid native chunk table")
    ends = struct.unpack_from(f"<{count}I", body, meta + 160)
    if len(body) != meta + 164 + count * 4:
        raise ValueError("Unexpected native metadata length")
    stream_name = raw[38 + body_size:].split(b"\0", 1)[0].decode("ascii")
    stream_path = (path.parent / stream_name).resolve()
    if not stream_path.is_relative_to(path.parent.resolve()):
        raise ValueError("Native stream path escapes resource directory")
    stream = stream_path.read_bytes()
    if not ends or ends[-1] != len(stream) or any(a >= z for a, z in zip((0,) + ends, ends)):
        raise ValueError("Native chunk bounds do not match stream")
    dxgi = struct.unpack_from("<I", low_dds, 128)[0]
    # Shipped resources store DDSD_LINEARSIZE here, not a row pitch.
    # Derive BC block bytes from DXGI, as required by the DDS format.
    block_size = 8 if dxgi in (71, 72) else 16
    if dxgi not in (71, 72, 77, 78, 83):
        raise ValueError("Unsupported or inconsistent block compression")
    low_h, low_w, linear_size = struct.unpack_from("<III", low_dds, 12)
    expected_size = max(1, (low_w + 3) // 4) * max(1, (low_h + 3) // 4) * block_size
    if linear_size != expected_size:
        raise ValueError(f"Embedded DDS LINEARSIZE is {linear_size}; expected {expected_size}")
    tile_width_blocks = 128 if block_size == 8 else 64
    columns = width // (tile_width_blocks * 4)
    rows = height // 256
    top_chunks = columns * rows
    if not columns or not rows or top_chunks > count:
        raise ValueError("Largest mip does not fit native chunks")
    pitch = width // 4 * block_size
    top = bytearray(pitch * (height // 4))
    previous = 0
    row_bytes = tile_width_blocks * block_size
    for index in range(top_chunks):
        tile = oodle.decompress(stream[previous:ends[index]], 65536)
        previous = ends[index]
        x, y = index % columns, index // columns
        for row in range(64):
            destination = (y * 64 + row) * pitch + x * row_bytes
            top[destination:destination + row_bytes] = tile[row * row_bytes:(row + 1) * row_bytes]
    header = bytearray(low_dds[:148])
    struct.pack_into("<I", header, 8, struct.unpack_from("<I", header, 8)[0] & ~0x20000)
    struct.pack_into("<III", header, 12, height, width, len(top))
    struct.pack_into("<I", header, 28, 1)
    return bytes(header) + bytes(top), {
        "width": width, "height": height, "dxgi": dxgi,
        "stream": stream_name, "streamed_mips": streamed_mips,
        "chunks": count, "top_chunks": top_chunks, "flags": flags,
        "low_mip_linear_size": linear_size,
    }
