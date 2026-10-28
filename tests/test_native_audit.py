"""Synthetic cosmetic UNIT suffix fixtures; real SDK integration runs in smoke."""
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from native_audit import material_bindings


class Reader:
    def __init__(self, data): self.data, self.offset = data, 0
    def take(self, size):
        value=self.data[self.offset:self.offset+size]; self.offset+=size
        if len(value)!=size: raise ValueError('truncated fixture')
        return value
    def u32(self): return struct.unpack('<I',self.take(4))[0]
    def array(self): self.take(self.u32())
    def u32_array(self): self.take(4*self.u32())


class NativeAuditTests(unittest.TestCase):
    def check(self, bindings):
        # Empty physics/terrain/render sections, followed by the native slot table.
        blob=b'\0'*85+struct.pack('<I',len(bindings))+b''.join(struct.pack('<IQ',*x) for x in bindings)
        sdk=SimpleNamespace(reference_skeleton=SimpleNamespace(_read_unit=lambda value:([],Reader(value))))
        return material_bindings(blob,sdk)

    def test_valid_material_binding(self):
        self.assertEqual(self.check([(12,12345)])[1],[(12,12345)])

    def test_zero_empty_and_duplicate_material_bindings_rejected(self):
        for bindings in ([],[(12,0)],[(12,12345),(12,67890)]):
            with self.subTest(bindings=bindings), self.assertRaises(ValueError): self.check(bindings)


if __name__=='__main__': unittest.main()
