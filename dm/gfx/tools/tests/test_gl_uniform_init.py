"""Compiler-backed defaults: arrays, folded constants, vectors, matrices and bools."""
import unittest,sys,tempfile,struct,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gl_uniform_init import constants, initial_block

class Defaults(unittest.TestCase):
 def test_compiler_and_layout(self):
  source='''#version 450
layout(location=0) out vec4 color;
uniform float w[3] = float[](0.2, 0.4, 0.6);
uniform vec3 tint = vec3(0.1 + 0.2, 0.5, 1.0);
uniform mat2 transform = mat2(2.0);
uniform bool enabled = true;
void main() { color=vec4(tint*w[1]*transform[0][0],float(enabled)); }
'''
  members=[dict(name='w',type='float',offset=0,array=[3],array_stride=16),dict(name='tint',type='vec3',offset=48),dict(name='transform',type='mat2',offset=64,matrix_stride=16),dict(name='enabled',type='bool',offset=96)]
  with tempfile.TemporaryDirectory() as td:
   b=bytes.fromhex(initial_block(source,'frag',Path(td)/'x',members,112))
  for off,want in [(0,.2),(16,.4),(32,.6),(48,.3),(52,.5),(56,1),(64,2),(68,0),(80,0),(84,2)]:self.assertAlmostEqual(struct.unpack_from('<f',b,off)[0],want,places=6)
  self.assertEqual(struct.unpack_from('<I',b,96)[0],1)
  self.assertEqual(b[4:16],bytes(12))
 def test_rejects_bad_instruction(self):
  blob=struct.pack('<6I',0x07230203,0x10000,0,1,0,0)
  with self.assertRaises(ValueError):constants(blob)
 def test_rejects_bad_header(self):
  for blob in (b'',bytes(20),b'abc'):
   with self.assertRaises(ValueError):constants(blob)
 def test_rejects_unresolved_initializer(self):
  # UniformConstant variable whose initializer is not a supported constant.
  blob=struct.pack('<10I',0x07230203,0x10000,0,8,0,(5<<16)|59,1,2,0,7)
  with self.assertRaises(ValueError):constants(blob)
 def test_rejects_layout_overflow(self):
  source='#version 450\nlayout(location=0) out vec4 color; uniform float x=0.5; void main(){ color=vec4(x); }'
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaises(ValueError):initial_block(source,'frag',Path(td)/'x',[dict(name='x',type='float',offset=16)],16)
 def test_no_defaults_preserves_zero(self):
  source='#version 450\nlayout(location=0) out vec4 color; uniform float x; void main(){ color=vec4(x); }'
  with tempfile.TemporaryDirectory() as td:b=initial_block(source,'frag',Path(td)/'x',[dict(name='x',type='float',offset=0)],16)
  self.assertEqual(bytes.fromhex(b),bytes(16))
if __name__=='__main__':unittest.main()
