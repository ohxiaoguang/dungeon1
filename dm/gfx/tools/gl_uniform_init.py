"""Recover GLSL link-time defaults before Vulkan's relaxed compiler drops them.

The OpenGL SPIR-V compiler folds constant expressions and keeps OpVariable
initializers; no hand-written GLSL expression evaluator or game-specific values.
"""
import re, struct, subprocess
from pathlib import Path


def constants(blob):
    if len(blob) < 20 or len(blob) % 4 or struct.unpack_from('<I', blob)[0] != 0x07230203:
        raise ValueError('malformed SPIR-V header')
    words = struct.unpack('<%dI' % (len(blob)//4), blob)
    names, values, variables = {}, {}, []
    i = 5
    while i < len(words):
        wc, op = words[i] >> 16, words[i] & 65535
        if not wc or i+wc > len(words): raise ValueError('malformed SPIR-V')
        a = words[i+1:i+wc]
        if op == 5: names[a[0]] = struct.pack('<%dI' % (len(a)-1), *a[1:]).split(b'\0')[0].decode()
        elif op == 43: values[a[1]] = list(a[2:])  # supported GL uniform types are 32-bit
        elif op in (41,42): values[a[1]] = [int(op == 41)]
        elif op == 44: values[a[1]] = sum((values[x] for x in a[2:]), [])
        elif op == 59 and len(a) == 4 and a[2] == 0: variables.append((a[1], a[3]))
        i += wc
    out = {}
    for n, v in variables:
        if n not in names or v not in values:
            raise ValueError('unsupported uniform initializer constant')
        out[names[n]] = values[v]
    return out


def initial_block(pp, stage, tmp, members, block_size):
    # Vulkan emits this warning precisely when the defaults are being discarded.
    source = re.sub(r'^\s*#version\s+[^\n]+', '#version 450', pp, count=1, flags=re.M)
    src, spv = str(tmp)+'.init.'+stage, str(tmp)+'.init.spv'
    Path(src).write_text(source)
    r = subprocess.run(['glslangValidator','-G','--aml','--amb','-S',stage,src,'-o',spv],capture_output=True,text=True)
    if r.returncode: raise ValueError('GL uniform initializer compile: '+(r.stdout+r.stderr)[-700:])
    defaults = constants(Path(spv).read_bytes())
    out = bytearray(block_size)
    for mb in members:
        if mb['name'] not in defaults: continue
        ty = mb['type']; mat = re.fullmatch(r'mat([234])',ty)
        rows = int(mat[1]) if mat else int(ty[-1]) if ty[-1:].isdigit() else 1
        cols = rows if mat else 1
        if ty not in ('float','int','uint','bool','vec2','vec3','vec4','ivec2','ivec3','ivec4','uvec2','uvec3','uvec4','mat2','mat3','mat4'):
            raise ValueError('unsupported uniform initializer type: '+ty)
        shape = mb.get('array', [1])
        if len(shape) != 1 or not shape[0]: raise ValueError('unsupported uniform initializer array')
        count = shape[0]; vals = defaults[mb['name']]
        if len(vals) != count*rows*cols: raise ValueError('uniform initializer shape: '+mb['name'])
        k = 0
        for a in range(count):
            for c in range(cols):
                for row in range(rows):
                    at = mb['offset'] + a*mb.get('array_stride',0) + c*mb.get('matrix_stride',0) + row*4
                    if at+4 > len(out): raise ValueError('uniform initializer layout bounds')
                    struct.pack_into('<I',out,at,vals[k]); k+=1
    return out.hex()
