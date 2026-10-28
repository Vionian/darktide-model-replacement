"""Darktide v67 texture writer, checked against limn ca9a36b texture.rs.

BC mip levels use 64 KiB Oodle blocks in row-major tiles. The low mips and
DX10 DDS header remain in the resource body; a 31-byte tail names the stream.
The game-supplied Oodle DLL is used locally and is never copied into the mod.
"""
import ctypes
import struct
import zlib
import numpy as np


class Oodle:
    def __init__(self, dll_path):
        self.dll = ctypes.CDLL(str(dll_path))
        self.compress_fn = self.dll.OodleLZ_Compress
        self.compress_fn.restype = ctypes.c_int64
        self.compress_fn.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int64,
                                    ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                                    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64]
        self.decode_fn = self.dll.OodleLZ_Decompress
        self.decode_fn.restype = ctypes.c_int64
        self.decode_fn.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_int64,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int64,
                                  ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int]

    def compress(self, data):
        source = ctypes.create_string_buffer(data)
        output = ctypes.create_string_buffer(len(data) + 65536)
        size = self.compress_fn(8, source, len(data), output, 4, None, None, None, None, 0)
        if not 0 < size <= len(output):
            raise ValueError("Oodle compression failed")
        packed = output.raw[:size]
        if self.decompress(packed, len(data)) != data:
            raise ValueError("Oodle compression round-trip failed")
        return packed

    def decompress(self, data, size):
        source = ctypes.create_string_buffer(data)
        output = ctypes.create_string_buffer(size)
        scratch = ctypes.create_string_buffer(0x100000)
        result = self.decode_fn(source, len(data), output, size, 1, 0, 3,
                                None, 0, None, None, scratch, len(scratch), 3)
        if result != size:
            raise ValueError("Oodle decompression failed")
        return output.raw


def pack_texture(dds, stream_name, oodle, profile_footer=None):
    if dds[:4] != b"DDS " or dds[84:88] != b"DX10":
        raise ValueError("Expected BC DX10 DDS")
    height, width = struct.unpack_from("<II", dds, 12)
    mip_count = struct.unpack_from("<I", dds, 28)[0]
    dxgi = struct.unpack_from("<I", dds, 128)[0]
    block_bytes = 8 if dxgi in (71, 72) else 16
    if dxgi not in (71, 72, 77, 78, 83):
        raise ValueError(f"Unsupported BC format: {dxgi}")
    tile_blocks_x = 128 if block_bytes == 8 else 64
    tile_blocks_y = 64
    mips = []
    offset = 148
    for mip in range(mip_count):
        w, h = max(1, width >> mip), max(1, height >> mip)
        size = max(1, (w+3)//4) * max(1, (h+3)//4) * block_bytes
        mips.append(dds[offset:offset+size])
        offset += size
    if offset != len(dds):
        raise ValueError("Invalid DDS mip lengths")
    stream_parts, cumulative_sizes, mip_records = [], [], []
    stream_decoded_bytes = 0
    streamed_mips = 0
    for mip, data in enumerate(mips):
        bx, by = max(1, (width >> mip)//4), max(1, (height >> mip)//4)
        if bx < tile_blocks_x or by < tile_blocks_y:
            break
        if bx % tile_blocks_x or by % tile_blocks_y:
            raise ValueError("Streamed mip is not tile aligned")
        blocks = np.frombuffer(data, dtype=np.uint8).reshape(by, bx, block_bytes)
        mip_records.append((stream_decoded_bytes, len(data)))
        stream_decoded_bytes += len(data)
        for y in range(0, by, tile_blocks_y):
            for x in range(0, bx, tile_blocks_x):
                tile = blocks[y:y+tile_blocks_y, x:x+tile_blocks_x].tobytes()
                if len(tile) != 65536:
                    raise ValueError("Invalid high mip tile")
                packed = oodle.compress(tile)
                stream_parts.append(packed)
                cumulative_sizes.append((cumulative_sizes[-1] if cumulative_sizes else 0) + len(packed))
        streamed_mips += 1
    if not streamed_mips:
        raise ValueError("Texture needs at least one streamed mip")
    low_header = bytearray(dds[:148])
    low_w, low_h = width >> streamed_mips, height >> streamed_mips
    # DDSD_LINEARSIZE describes the complete first BC mip, not one block row.
    # Match both the DDS header contract and the shipped reference textures.
    struct.pack_into("<III", low_header, 12, low_h, low_w, len(mips[streamed_mips]))
    struct.pack_into("<I", low_header, 28, mip_count-streamed_mips)
    low_data = b"".join(mips[streamed_mips:])
    low_dds = bytes(low_header) + low_data
    packed_low = oodle.compress(low_dds)
    low_offset = 0
    for data in mips[streamed_mips:]:
        mip_records.append((low_offset, len(data)))
        low_offset += len(data)
    if len(mip_records) > 16:
        raise ValueError("Too many mip records")
    table = b"".join(struct.pack("<II", *record) for record in mip_records).ljust(128, b"\0")
    num_chunks = len(cumulative_sizes)
    metadata = (struct.pack("<5I", 67, 257 if dxgi in (72, 78) else 1, streamed_mips, width, height)
                + table + struct.pack("<IIHH", 8+num_chunks*4, num_chunks, 0, num_chunks)
                + struct.pack(f"<{num_chunks}I", *cumulative_sizes) + struct.pack("<I", zlib.crc32(dds) if profile_footer is None else profile_footer))
    body = struct.pack("<III", 1, len(packed_low), len(low_dds)) + packed_low + metadata
    tail = stream_name.encode("ascii").ljust(31, b"\0")
    if len(tail) != 31:
        raise ValueError("Native texture path exceeds 31 bytes")
    # Decode every tile and reassemble the original BC bytes in mip order.
    restored = []
    chunk_index = 0
    for mip in range(streamed_mips):
        bx, by = (width >> mip)//4, (height >> mip)//4
        blocks = np.empty((by, bx, block_bytes), dtype=np.uint8)
        for y in range(0, by, tile_blocks_y):
            for x in range(0, bx, tile_blocks_x):
                tile = oodle.decompress(stream_parts[chunk_index], 65536)
                blocks[y:y+tile_blocks_y, x:x+tile_blocks_x] = np.frombuffer(tile, dtype=np.uint8).reshape(tile_blocks_y, tile_blocks_x, block_bytes)
                chunk_index += 1
        restored.append(blocks.tobytes())
    if b"".join(restored) + low_data != dds[148:]:
        raise ValueError("Texture mip stream round-trip failed")
    return body, tail, b"".join(stream_parts)
