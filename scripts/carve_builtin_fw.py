#!/usr/bin/env python3
"""Recover CONFIG_EXTRA_FIRMWARE blobs from a stock kernel Image (the source drop may ship without them).
The kernel's .builtin_fw table holds (name_ptr, data_ptr, size) triples with link-time virtual addresses;
we locate each firmware name string, find the table entry pointing at it, and copy the data out.
Usage: carve_builtin_fw.py <Image> <out-dir>"""
import os, re, struct, sys
img, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
k = open(img, 'rb').read(); text_off = struct.unpack_from('<Q', k, 8)[0]
BASES = (0xffffffc0, 0xffff8000, 0xffffff80)   # KIMAGE_VADDR high words seen on arm64 5.x
n = 0
for m in re.finditer(rb'[A-Za-z0-9_./-]+\.(?:bin|fw|img|dump)\x00', k):
    name_off = m.start(); name = k[name_off:m.end()-1].decode()
    low = (name_off + 0x10000000 + text_off) & 0xffffffff
    for hi in BASES:
        for t in re.finditer(re.escape(struct.pack('<Q', (hi << 32) | low)), k):
            o = t.start()
            if o % 8: continue
            dptr, size = struct.unpack_from('<QQ', k, o + 8)
            if not (0 < size < 16 << 20) or (dptr >> 32) != hi: continue
            doff = dptr - (hi << 32) - 0x10000000 - text_off
            if not (0 <= doff < len(k)): continue
            path = os.path.join(out, os.path.basename(name)); open(path, 'wb').write(k[doff:doff+size])
            print(f'{name}: table@{o:#x} data@{doff:#x} size={size} -> {path}'); n += 1
print('firmware blobs recovered:', n)
