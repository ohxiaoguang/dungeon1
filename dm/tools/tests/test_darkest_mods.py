"""Execute the build-scoped XML getter patches as AArch64 (pip install unicorn).

Synthetic XML nodes exercise the actual replacement bytes, including the call
ABI, destinations, bounded UTF-8 copies and null values. Real-game scanner and
save/load checks are recorded separately in the iOS multi-MOD validation note.
"""
import importlib.util
from pathlib import Path
import struct
import unittest

try:
    from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
    from unicorn.arm64_const import (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2,
                                    UC_ARM64_REG_X8, UC_ARM64_REG_X19, UC_ARM64_REG_LR,
                                    UC_ARM64_REG_PC)
except ImportError:
    Uc = None

PATCH = Path(__file__).resolve().parents[2] / 'games/01008F1008DA6000/patches.py'
spec = importlib.util.spec_from_file_location('darkest_patches', PATCH)
patches = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patches)
BUILD = 'ff2bf22565188d11ea0981ee0e2b53ce'


@unittest.skipIf(Uc is None, 'AArch64 patch execution requires unicorn')
class XmlMetadata(unittest.TestCase):
    def execute(self, cut, value, field):
        off, _, code, _ = cut
        machine = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        machine.mem_map(off & ~4095, 4096)
        machine.mem_write(off, bytes.fromhex(code))
        machine.mem_map(0xe6a000, 4096)  # the unchanged game's strlcpy PLT
        machine.mem_map(0x2000000, 0x4000)
        obj, node, text = 0x2000000, 0x2001000, 0x2002000
        machine.mem_write(obj, b'\xa5' * 4096)
        machine.mem_write(node + 8, struct.pack('<Q', text if value is not None else 0))
        if value is not None:
            machine.mem_write(text, value.encode() + b'\0')
        machine.reg_write(UC_ARM64_REG_X8, node)
        machine.reg_write(UC_ARM64_REG_X19, obj)
        calls = []

        def call(uc, address, size, _):
            if address != 0xe6a0e0:
                return
            dst, src, cap = (uc.reg_read(r) for r in
                             (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2))
            data = bytes(uc.mem_read(src, 2048)).split(b'\0', 1)[0]
            calls.append((dst, src, cap))
            uc.mem_write(dst, data[:cap - 1] + b'\0')
            uc.reg_write(UC_ARM64_REG_X0, len(data))
            uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_LR))

        machine.hook_add(UC_HOOK_CODE, call)
        machine.emu_start(off, off + len(bytes.fromhex(code)), count=50)
        data = bytes(machine.mem_read(obj, 4096))
        if value is None:
            self.assertEqual(calls, [])
            self.assertEqual(data, b'\xa5' * 4096)
            return None
        self.assertEqual(calls, [(obj + field, text, 0x200)])
        result = value.encode()[:511] + b'\0'
        self.assertEqual(data[field:field + len(result)], result)
        self.assertEqual(data[:field], b'\xa5' * field)
        self.assertEqual(data[field + len(result):], b'\xa5' * (4096 - field - len(result)))
        return result[:-1]

    def test_three_mods_have_distinct_titles(self):
        titles = ['Inventory Expansion Lite', 'Curio Hints V1.5 \u4e92\u52a8\u63d0\u793a',
                  'Stacking Inventory']
        actual = [self.execute(patches.CUTS[BUILD][0], title, 0x800) for title in titles]
        self.assertEqual(len(set(actual)), 3)

    def test_each_preview_keeps_its_own_filename(self):
        for icon in ['preview_icon.png', 'art/custom icon.png', '\u56fe\u6807.png']:
            with self.subTest(icon=icon):
                self.execute(patches.CUTS[BUILD][1], icon, 0x200)

    def test_empty_and_null_nodes(self):
        for cut, field in zip(patches.CUTS[BUILD], [0x800, 0x200]):
            self.execute(cut, '', field)
            self.execute(cut, None, field)

    def test_long_values_cannot_overwrite_adjacent_project_fields(self):
        for cut, field in zip(patches.CUTS[BUILD], [0x800, 0x200]):
            self.execute(cut, 'x' * 900, field)


class Scope(unittest.TestCase):
    def test_only_the_registered_130_build_is_modified(self):
        self.assertEqual(set(patches.CUTS), {BUILD})
        self.assertEqual([entry[0] for entry in patches.CUTS[BUILD]], [0x8c69b8, 0x8c71e0])
        self.assertNotIn('0d07c2465fb869fdf0944090387d1550', patches.CUTS)


if __name__ == '__main__':
    unittest.main()
