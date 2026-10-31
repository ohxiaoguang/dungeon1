#!/bin/sh
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
exec "${PYTHON:-python3}" "$ROOT/scripts/dungeon1_build.py" --target mac "$@"
