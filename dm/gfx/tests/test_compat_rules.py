"""Synthetic rule contracts; contains no extracted or translated game shaders."""
from pathlib import Path
import sys
import unittest
import struct
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/easf'))
import fxo
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import dmsh_bindless
import dmsh_ptrfix
import dmsh_fetch


class ExtractionRules(unittest.TestCase):
    def test_headerless_compute_skips_interposed_constants(self):
        control = bytearray(0x760)
        control[:4] = fxo.CTL_MAGIC
        struct.pack_into('<I', control, 0x20, len(control))
        struct.pack_into('<I', control, 0x6f0, len(control) + 0x180)
        code = bytes(range(32))
        struct.pack_into('<I', control, 0x704, len(code))
        struct.pack_into('<3I', control, 0x748, 32, 1, 1)
        container = bytearray(0x18) + control + bytes([0xcc]) * 0x180 + code
        container[:8] = b'NXSHADER'
        container[0x10:0x14] = b'GLSL'
        struct.pack_into('<I', container, 0x14, len(container) - 0x10)
        programs = fxo.programs(container)
        self.assertEqual(len(programs), 1)
        self.assertEqual(programs[0][0], 'cs')
        self.assertEqual(programs[0][3], code)
        self.assertEqual(programs[0][1], fxo.skey(control, code))


class BindlessRules(unittest.TestCase):
    def test_pool_ids_and_argument_layout(self):
        source = '''struct spvDescriptorSetBuffer0
{
    array<texture2d<float>, 32> tex_cb0_40000000 [[id(1)]];
    array<sampler, 32> sam_cb0_40000000 [[id(33)]];
    const device uint* tail [[id(65)]];
};
uint _1 = min(handle & 1048575u, 31u);
uint _2 = min(handle >> 20u, 31u);
uint _3 = min(unrelated, 31u);
a = tex_cb0_40000000[int(_1)];
b = sam_cb0_40000000[int(_2)];
'''
        lowered, applied = dmsh_bindless.apply(source)
        self.assertTrue(applied)
        self.assertIn('array<texture2d<float>, 16384>', lowered)
        self.assertIn('array<sampler, 4096>', lowered)
        self.assertIn('sam_cb0_40000000 [[id(16385)]]', lowered)
        self.assertIn('tail [[id(20481)]]', lowered)
        self.assertIn('min(handle & 1048575u, 16383u)', lowered)
        self.assertIn('min(handle >> 20u, 4095u)', lowered)
        self.assertIn('min(unrelated, 31u)', lowered)

    def test_unknown_direct_layout_is_rejected(self):
        source = 'struct spvDescriptorSetBuffer0 {\n array<sampler, 16> sam_cb0_40000000 [[id(0)]];\n};'
        with self.assertRaises(ValueError):
            dmsh_bindless.apply(source)

    def test_ordinary_shader_is_unchanged(self):
        source = 'struct spvDescriptorSetBuffer0 {\n texture2d<float> tex [[id(0)]];\n};'
        self.assertEqual(dmsh_bindless.apply(source), (source, False))


class PointerRules(unittest.TestCase):
    def test_vertex_read_gets_runtime_base_and_bounds(self):
        source = '''
struct Data { uint _m0[1024]; };
struct spvDescriptorSetBuffer0
{
    const device Data* vp_s0 [[id(0)]];
};
static inline __attribute__((always_inline))
int indirect(thread const int& _1, thread const int& _2)
{
    return 0;
}
vertex int main0(constant spvDescriptorSetBuffer0& spvDescriptorSet0 [[buffer(0)]])
{
    return indirect(_3, _4);
}
'''
        lowered, info = dmsh_ptrfix.apply(source, 'vs')
        self.assertTrue(info['applied'])
        self.assertEqual(info['entries'], 1)
        self.assertEqual(info['reads'], 1)
        self.assertIn('[[buffer(13)]]', lowered)
        self.assertIn('_pf_a - _pf_b.base', lowered)
        self.assertIn('_pf_off > _pf_b.limit - 4ul', lowered)
        self.assertEqual(info['pool_slot'], 12)
        self.assertIn('[[buffer(12)]]', lowered)
        self.assertIn('indirect(_3, _4, _pf_pool, _pf_b)', lowered)
        other, info = dmsh_ptrfix.apply(source, 'ps')
        self.assertEqual(source, other)
        self.assertFalse(info['applied'])


class VariantCacheRules(unittest.TestCase):
    def test_integer_entry_does_not_change_tile_variant(self):
        primary = """using namespace metal;
struct main0_out
{
    float4 m_0 [[color(0)]];
};
fragment main0_out main0()
{
    main0_out out = {};
    out.m_0 = float4(0);
    return out;
}
"""
        cached = primary + '\nstruct main0_out_u\n{\n uint4 m_0 [[color(0)]];\n};\nfragment main0_out_u main0_u() {}\n'
        self.assertEqual(dmsh_fetch.variant(primary, [], True), dmsh_fetch.variant(cached, [], True))


if __name__ == '__main__':
    unittest.main()
