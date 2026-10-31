"""The iOS generator must keep Make output in its caller's Gen directory."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]


class GenBuildTests(unittest.TestCase):
    def test_relative_gen_is_absolute_for_both_make_invocations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            host = root / 'host'
            host.mkdir()
            (host / 'main.c').write_text('int main(void) { return 0; }\n')
            (root / 'Gen').mkdir()
            tools = root / 'tools'
            tools.mkdir()
            make = tools / 'make'
            make.write_text('#!' + sys.executable + '\n'
                            'import os,sys\n'
                            'from pathlib import Path\n'
                            'with open(os.environ["GEN_LOG"], "a") as f: f.write(os.environ["GEN"]+"\\n")\n'
                            'if "-n" in sys.argv: print("clang -I"+os.environ["GEN"]+" main.c -o dmhost")\n')
            make.chmod(0o755)
            result = subprocess.run([sys.executable, str(REPO / 'dm/ios/tools/gen_build.py'),
                                     str(host), 'Gen'], cwd=root, check=True, capture_output=True,
                                    text=True, env=dict(os.environ, PATH=str(tools)+os.pathsep+os.environ['PATH'],
                                                       GEN_LOG=str(root / 'make.log')))
            self.assertEqual((root / 'make.log').read_text().splitlines(), [str(root / 'Gen')] * 2)
            self.assertIn(str(root / 'Gen'), result.stdout)
            self.assertEqual((root / 'Gen/main/main.c').resolve(), host / 'main.c')
            self.assertFalse((host / 'Gen').exists())


if __name__ == '__main__':
    unittest.main()
