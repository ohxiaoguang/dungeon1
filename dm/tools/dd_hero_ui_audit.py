#!/usr/bin/env python3
"""Read-only RTTI/vtable inventory for the supported DD 1.3.0 UI.

Usage: dd_hero_ui_audit.py /private/ExeFS
Output is compatibility metadata, never a runtime Hero layout or proof that a
callable is safe to invoke. No game bytes or text resources are exported.
"""
import argparse
import json
import re
import struct
from pathlib import Path

import nsoseg

BUILDS = {"main": "ff2bf22565188d11ea0981ee0e2b53ce",
          "sdk": "b33804825108340e4cad9d080a636a3f"}
PATTERN = re.compile(rb"(?:ShowBuffIconTooltip|Get\w*BuffInstanceList|"
                     rb"StatAddAdditionalTooltipBuffLines|ShowSelectedHero)")


def inventory(exefs):
    images = {}
    for module, expected in BUILDS.items():
        image, build, *_ = nsoseg.load(exefs / module, bss=False)
        if build != expected:
            raise ValueError(f"Unsupported {module} Build ID: {build}")
        images[module] = image
    image = images["main"]
    # Reverse index of aligned image-relative pointers. These are static image
    # relocations, not addresses to dereference in a running host.
    refs = {}
    for offset in range(0, len(image) - 7, 8):
        value = struct.unpack_from("<Q", image, offset)[0]
        if 0 < value < len(image):
            refs.setdefault(value, []).append(offset)
    rows = []
    for match in re.finditer(rb"[ -~]{8,}\x00", image):
        name = match.group()[:-1]
        if not name.startswith(b"NSt3__110__function6__funcI") or not PATTERN.search(name):
            continue
        for name_ref in refs.get(match.start(), []):
            typeinfo = name_ref - 8
            if typeinfo < 0:
                continue
            for table_ref in refs.get(typeinfo, []):
                vtable = table_ref + 8
                if vtable + 0x38 > len(image):
                    continue
                call = struct.unpack_from("<Q", image, vtable + 0x30)[0]
                if 0 < call < len(image):
                    rows.append(dict(name=name.decode("ascii"),
                                     typeinfo=hex(typeinfo), vtable=hex(vtable),
                                     call_slot_30=hex(call)))
    return dict(builds=BUILDS, evidence="static RTTI only; not runtime validated", callables=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exefs", type=Path)
    args = parser.parse_args()
    print(json.dumps(inventory(args.exefs), indent=2))


if __name__ == "__main__":
    main()
