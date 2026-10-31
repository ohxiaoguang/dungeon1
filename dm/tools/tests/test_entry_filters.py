"""The rewriter's entry filters (FILTERS of the patch files, patch_nso.py "site_filter"): the stub an integer/void entry filter emits.

A filter is entered with the caller's `b` (no link), so the guest's original LR, FP and SP still describe the original call when the stub runs: allowing has to leave them, and the
original x0-x7 arguments, exactly as they were, then execute the original entry instruction; denying has to return integer zero before any of it. The decision comes from dm_gate,
which every gate reaches through the thread slot; the stub therefore restores only x0 itself and leaves the other argument registers to the gate's own save area (dm/host/entry.S
saves x0-x30 there and reads them back).

Here without game files: patch_nso.py is a command-line program whose top level loads and rewrites an image, so only these functions are compiled, as test_spin_waits.py does for
the spin wait search. Every assertion is about the words actually emitted: which registers each one writes, how far each branch goes, and where the original instruction runs.
Host runtime behaviour (how the allow/deny decision itself is taken) is not covered here; the DD adapter's own runtime validation is in dm/host/hle_dd_touch.c.
"""
import ast
import re
import struct
import sys
import unittest
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from capstone.arm64 import ARM64_OP_MEM as CS_OP_MEM

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import nso_asm  # noqa: E402

tree = ast.parse((TOOLS / 'patch_nso.py').read_text())
NAMES = {'site_filter', 'emit_gate_call', 'emit_slot_addr', 'emit_key_addr'}
BODY = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in NAMES]
KEY_PAGE_OFF, PATCH_OFF = 0x4000, 0x1000000

md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
md.detail = True

# Original offsets and words of entries a filter may be asked for: an ordinary relocatable stack prologue (patch_nso.py asserts those two mnemonics)
ENTRIES = {'sub sp, sp, #0x80': (0xe3b5a0, 0xd10203ff), 'stp x29, x30, [sp, #-0x20]!': (0xe3d7d0, 0xa9be7bfd),
           'sub sp, sp, #0x10': (0x1000, 0xd10043ff)}


def emit_stub(off, fid, word):
    """Run the rewriter's site_filter on one original entry word: its words, and the gate row it registered."""
    words, gates, fix, patch = [], [], [], bytearray()   # patch is the rewriter's own buffer: its length numbers the key-page fixups

    def emit(w, kind=None):
        if kind: fix.append((len(patch) // 4, kind))
        words.append(w & 0xFFFFFFFF); patch.extend(struct.pack('<I', w & 0xFFFFFFFF))

    scope = {'emit': emit, 'here': lambda: PATCH_OFF + len(patch), 'gates': gates, 'fix': fix, 'patch': patch, 'struct': struct,
             're': re, 'KEY_PAGE_OFF': KEY_PAGE_OFF, 'KEY_INDEX': {'KGATE': 3}, 'has18': has18, 'dis': decode}
    for name in dir(nso_asm):
        if not name.startswith('_'): scope[name] = getattr(nso_asm, name)
    exec(compile(ast.Module(body=BODY, type_ignores=[]), str(TOOLS / 'patch_nso.py'), 'exec'), scope)
    start = scope['site_filter'](off, fid, word)
    return start, words, gates, fix


def decode(w, addr):
    (i,) = md.disasm(struct.pack('<I', w), addr)
    return i


def dis(words, base):
    return list(md.disasm(struct.pack('<' + 'I' * len(words), *words), base))


SPECIAL = {'fp': 29, 'lr': 30, 'xzr': 31, 'wzr': 31, 'sp': 31}   # capstone prints these by name, not by number


def num(name):
    m = re.fullmatch(r'[xw](\d+)', name or '')
    return int(m.group(1)) if m else SPECIAL.get(name or '')


def writes(ins):
    return {num(ins.reg_name(r)) for r in ins.regs_access()[1]}


def has18(ins):
    return re.search(r'\b[xw]18\b', ins.op_str) is not None


def frame_size(ins):
    return int(re.search(r'#(-?0x[0-9a-f]+)', ins.op_str).group(1), 16)


class Entry(unittest.TestCase):
    """What site_filter accepts: an ordinary relocatable stack prologue only."""
    REFUSED = {'ret': 0xd65f03c0, 'adrp x0, #0x1000': 0xb0000000, 'b #4': 0x14000001, 'bl #4': 0x94000001,
               'mov x0, x1': 0xaa0103e0, 'sub x0, x0, #1': 0xd1000400, 'stp x29, x30, [x0]': 0xa9007ba0, 'mov x18, x0': 0xaa0003f2,
               'stp x29, x30, [sp, #0x10]': 0xa9017bfd}   # no frame opened at the entry: sp is not moved here

    def test_accepts_the_two_prologue_forms(self):
        for name, (off, word) in ENTRIES.items():
            with self.subTest(entry=name):
                start, words, gates, fix = emit_stub(off, 1, word)
                self.assertTrue(words)
                self.assertEqual(gates, [(start + 4 * 9, 'filter', 1, off)])   # the row the host reads from gates.tsv

    def test_refuses_anything_but_a_stack_prologue(self):
        for name, word in self.REFUSED.items():
            with self.subTest(instruction=name):
                with self.assertRaises(AssertionError, msg=f'{name} must not be taken as a filter entry'):
                    emit_stub(0x1000, 1, word)


class Stub(unittest.TestCase):
    def stub(self, off, word, fid=1):
        start, words, gates, fix = emit_stub(off, fid, word)
        return start, dis(words, start), fix

    def test_frame_is_one_matching_pair(self):
        for name, (off, word) in ENTRIES.items():
            with self.subTest(entry=name):
                start, ins, fix = self.stub(off, word)
                cbz = next(i for i in ins if i.mnemonic == 'cbz')
                pre = [i for i in ins if i.mnemonic == 'stp' and 'x29, x30, [sp' in i.op_str and ']!' in i.op_str and i.address < cbz.address]
                post = [i for i in ins if i.mnemonic == 'ldp' and 'x29, x30, [sp],' in i.op_str]
                self.assertEqual(len(pre), 1, 'one frame')
                self.assertEqual(len(post), 2, 'one restore each on the allow and the deny path')
                self.assertEqual(pre[0].address, start, 'the frame is opened first')
                size = frame_size(pre[0])
                self.assertTrue(size < 0 and -size % 16 == 0, f'the frame keeps sp 16-byte aligned: {size:#x}')
                for i in post: self.assertEqual(frame_size(i) if '#' in i.op_str else None, -size)

    def test_gate_call_entry_and_return_point(self):
        off, word = ENTRIES['sub sp, sp, #0x80']
        start, ins, fix = self.stub(off, word)
        # x30 = the address in thread slot KGATE, read through the key page: the same entry every gate uses.
        self.assertEqual((ins[2].mnemonic, ins[2].op_str), ('mrs', 'x30, tpidrro_el0'))
        self.assertEqual(ins[3].mnemonic, 'adrp')
        self.assertEqual(ins[4].op_str, 'x29, [x29, #0x18]')     # KGATE index 3, eight bytes apart
        self.assertEqual(ins[5].op_str, 'x30, x30, x29')
        self.assertEqual(ins[6].op_str, 'x30, [x30]')
        blr = [i for i in ins if i.mnemonic == 'blr']
        self.assertEqual((len(blr), blr[0].op_str), (1, 'x30'))
        # The host identifies a gate by the return point the blr left: it is what gates.tsv lists.
        self.assertEqual(emit_stub(off, 1, word)[2], [(blr[0].address + 4, 'filter', 1, off)])
        self.assertTrue(fix, 'the key-page address is a fixup, like every other slot reference')

    def test_borrowed_frame_pointer_is_restored_before_the_call(self):
        # emit_slot_addr borrows x29 to fetch the gate address; the x29 the host's crash walk reads must be the guest's.
        start, ins, fix = self.stub(*ENTRIES['sub sp, sp, #0x80'])
        blr = next(i for i in ins if i.mnemonic == 'blr')
        restore = next(i for i in ins if i.mnemonic == 'ldr' and i.op_str == 'x29, [sp]')
        borrow = [i for i in ins if i.address < restore.address and 29 in writes(i)]
        self.assertTrue(borrow, 'the key-page address is fetched through a borrowed register')
        self.assertLess(max(i.address for i in borrow), restore.address)
        self.assertLess(restore.address, blr.address)
        self.assertFalse([i for i in ins if restore.address < i.address < blr.address], 'nothing runs between the restore and the call')

    def test_only_the_first_argument_is_saved_by_the_stub(self):
        start, ins, fix = self.stub(*ENTRIES['sub sp, sp, #0x80'])
        blr = next(i for i in ins if i.mnemonic == 'blr')
        saved = [i for i in ins if i.mnemonic == 'str' and i.op_str.startswith('x0, [sp,')]
        self.assertEqual(len(saved), 1, 'the decision overwrites x0, so the original x0 is the one argument saved here')
        self.assertLess(saved[0].address, blr.address)
        slot = int(saved[0].op_str.rsplit('#', 1)[1].rstrip(']'), 16)
        self.assertTrue(0 <= slot < -frame_size(ins[0]), 'the slot lies inside the stub\'s own frame, never below sp')
        for i in ins:
            if i is saved[0] or i.mnemonic == 'blr': continue
            bad = {r for r in writes(i) if r is not None and 1 <= r <= 28} - {29}
            self.assertFalse(bad, f'{i.mnemonic} {i.op_str} writes x{bad}')

    def test_allow_path_runs_the_original_entry_unchanged(self):
        for name, (off, word) in ENTRIES.items():
            with self.subTest(entry=name):
                start, ins, fix = self.stub(off, word)
                cbz = next(i for i in ins if i.mnemonic == 'cbz')
                deny = cbz.operands[-1].imm
                allow = [i for i in ins if cbz.address < i.address < deny]
                self.assertEqual([i.mnemonic for i in allow[:2]], ['ldr', 'ldp'])
                self.assertEqual(allow[0].op_str, 'x0, [sp, #0x10]', 'the original first argument is back before anything else')
                self.assertTrue(allow[1].op_str.startswith('x29, x30, [sp],'), 'LR and FP restored and sp back at entry')
                self.assertEqual(struct.unpack('<I', allow[2].bytes)[0], word, 'the original entry instruction itself')
                self.assertEqual(allow[3].mnemonic, 'b')
                self.assertEqual(allow[3].operands[0].imm, off + 4, 'then control goes to the rest of the original function')

    def test_deny_path_returns_zero_without_running_anything_original(self):
        for name, (off, word) in ENTRIES.items():
            with self.subTest(entry=name):
                start, ins, fix = self.stub(off, word)
                cbz = next(i for i in ins if i.mnemonic == 'cbz')
                self.assertEqual(cbz.op_str.split(',')[0], 'x0', 'zero means deny, exactly what the filter callback returns')
                self.assertEqual(cbz.operands[-1].imm, start + 4 * 14, 'the branch lands on the deny path')
                path = [i for i in ins if i.address >= cbz.operands[-1].imm]
                self.assertTrue(path[0].op_str.startswith('x29, x30, [sp],'), 'sp, FP and LR back at entry before returning')
                self.assertEqual((path[1].mnemonic, path[1].operands[1].imm, writes(path[1])), ('mov', 0, {0}))
                self.assertEqual(path[2].mnemonic, 'ret')
                self.assertEqual(len(path), 3)
                self.assertNotIn(word, [struct.unpack('<I', i.bytes)[0] for i in path], 'no original instruction runs on deny')

    def test_platform_register_and_frame_only_memory(self):
        for name, (off, word) in ENTRIES.items():
            with self.subTest(entry=name):
                start, ins, fix = self.stub(off, word)
                adrp = []
                for i in ins:
                    self.assertFalse(has18(i), f'{i.mnemonic} {i.op_str}: x18 is the Apple platform register')
                    self.assertNotIn(i.mnemonic, ('adr', 'bl', 'cbnz', 'tbz', 'tbnz'))
                    if i.mnemonic == 'adrp': adrp.append(i)
                    if i.mnemonic in ('str', 'stp', 'ldp', 'ldr'):
                        mem = [o for o in i.operands if o.type == CS_OP_MEM]
                        self.assertTrue(mem, f'{i.mnemonic} {i.op_str}: not a memory operand')
                        base = i.reg_name(mem[-1].mem.base)
                        # Its own frame, or the borrowed x29 holding the key page address: no guest memory is written or read here.
                        self.assertIn(base, ('sp', 'x29', 'fp', 'x30', 'lr'), f'{i.mnemonic} {i.op_str}: anchored on {base}')   # capstone names x29 'fp' and x30 'lr'
                        if base == 'sp':
                            off_in_frame = mem[-1].mem.disp
                            self.assertTrue(0 <= off_in_frame < 32 or i.mnemonic in ('ldp', 'stp'),
                                            f'{i.mnemonic} {i.op_str}: outside its own 32-byte frame')
                self.assertEqual(len(adrp), 1, 'one PC-relative key page address, recorded for the loader like every other slot reference')
                self.assertEqual(len(fix), 1)


if __name__ == '__main__':
    unittest.main()
