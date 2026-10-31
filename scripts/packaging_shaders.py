#!/usr/bin/env python3
"""Run the shared Shader source and compiler pipeline from a reviewed request."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.packaging_gui.engine import Request
from tools.packaging_gui.shader_build import generate

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    args = parser.parse_args()
    generate(Request(**json.loads(args.request.read_text())))
