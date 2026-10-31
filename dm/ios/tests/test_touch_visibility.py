"""Exercise the visibility and layout-cycle policy used by the native touch overlay, without UIKit."""
from pathlib import Path
import subprocess
import tempfile
import unittest

class Visibility(unittest.TestCase):
    def test_switch_controller_and_layout_combinations(self):
        header = Path(__file__).resolve().parents[1] / 'Sources/TouchControlVisibility.h'
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'check.c'
            # Expected policy states, independently enumerated: controller presence
            # dominates both visuals, while 2D retains the pad without a right visual.
            source.write_text('#include <assert.h>\n#include "' + str(header) + '"\n'
                'int main(void) { const int cases[][6] = {'
                '{0,0,0,0,0,0},{0,0,0,1,0,0},{0,0,1,0,0,0},{0,0,1,1,0,0},'
                '{0,1,0,0,0,0},{0,1,0,1,0,0},{0,1,1,0,0,0},{0,1,1,1,0,0},'
                '{1,0,0,0,1,0},{1,0,0,1,1,0},{1,0,1,0,1,0},{1,0,1,1,1,1},'
                '{1,1,0,0,0,0},{1,1,0,1,0,0},{1,1,1,0,0,0},{1,1,1,1,0,0}};'
                'for(unsigned i=0;i<sizeof cases/sizeof cases[0];i++) {'
                'const int *c=cases[i]; int pad=dm_touch_pad_visible(c[0],c[1]);'
                'assert(pad==c[4]); assert((pad&&dm_touch_right_visible(c[3],c[2]))==c[5]);'
                '} return 0; }')
            binary = Path(root) / 'check'
            subprocess.run(['clang','-Wall','-Werror',str(source),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)

    def test_layout_cycle_is_tap_2d_3d_tap_and_takes_no_mode_argument(self):
        header = Path(__file__).resolve().parents[1] / 'Sources/TouchControlVisibility.h'
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'cycle.c'
            # The cycle is one closed ring over the three persisted values, with no way to
            # express a console mode: the docked/handheld distinction cannot come back.
            source.write_text('#include <assert.h>\n#include "' + str(header) + '"\n'
                'int main(void) {'
                'assert(dm_touch_next_layout(2) == 0); assert(dm_touch_next_layout(0) == 1);'
                'assert(dm_touch_next_layout(1) == 2);'
                'int l = 2; for (int i = 0; i < 6; i++) l = dm_touch_next_layout(l);'
                'assert(l == 2);'
                'return 0; }')
            binary = Path(root) / 'cycle'
            subprocess.run(['clang','-Wall','-Werror',str(source),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)

if __name__ == '__main__':
    unittest.main()
