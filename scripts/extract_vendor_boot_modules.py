# /// script
# requires-python = ">=3.10"
# dependencies = ["lz4==4.4.4"]
# ///
"""Extract *.ko (and modules.* lists) from a vendor_boot v3/v4 image's ramdisk(s)."""
import struct, sys, os, gzip, io
import lz4.frame
img, out = sys.argv[1], sys.argv[2]
d = open(img, 'rb').read()
assert d[:8] == b'VNDRBOOT', d[:8]
hv, page = struct.unpack_from('<II', d, 8)
kaddr, raddr, rsize = struct.unpack_from('<III', d, 16)
cmdline = d[28:28+2048].split(b'\0')[0].decode(errors='replace')
tags_addr = struct.unpack_from('<I', d, 2076)[0]
name = d[2080:2096].split(b'\0')[0]
hsize, dtb_size, dtb_addr = struct.unpack_from('<IIQ', d, 2096)
print(f'header v{hv} page {page} ramdisk {rsize} dtb {dtb_size} name {name!r}')
print('cmdline:', cmdline[:400])
o = (hsize + page - 1)//page*page
ramdisk = d[o:o+rsize]
o += (rsize + page - 1)//page*page
dtb = d[o:o+dtb_size]; o += (dtb_size + page - 1)//page*page
entries = []
if hv >= 4:
    tsize, tnum, tesize, bcsize = struct.unpack_from('<IIII', d, 2112)
    table = d[o:o+tsize]
    for i in range(tnum):
        e = table[i*tesize:(i+1)*tesize]
        rs, ro, rt = struct.unpack_from('<III', e, 0)
        rn = e[12:12+32].split(b'\0')[0].decode()
        entries.append((rn, ro, rs, rt))
    print('ramdisk table:', entries, 'bootconfig', bcsize)
else:
    entries = [('vendor_ramdisk', 0, rsize, 0)]
open(os.path.join(out, 'dtb.bin'), 'wb').write(dtb)
def decompress(b):
    if b[:4] == b'\x04\x22\x4d\x18':
        return lz4.frame.decompress(b)
    if b[:2] == b'\x1f\x8b':
        return gzip.decompress(b)
    if b[:4] == b'\x02\x21\x4c\x18':  # legacy lz4 frame
        outb = bytearray(); p = 4
        import lz4.block
        while p + 4 <= len(b):
            n = struct.unpack_from('<I', b, p)[0]; p += 4
            if n == 0x184c2102: continue
            outb += lz4.block.decompress(b[p:p+n], uncompressed_size=8*1024*1024); p += n
        return bytes(outb)
    return b
def walk_cpio(c):
    p = 0
    while p + 110 <= len(c):
        assert c[p:p+6] in (b'070701', b'070702'), c[p:p+6]
        f = [int(c[p+6+i*8:p+14+i*8], 16) for i in range(13)]
        namesize, filesize = f[11], f[6]
        nm = c[p+110:p+110+namesize-1].decode()
        p = (p + 110 + namesize + 3) & ~3
        data = c[p:p+filesize]
        p = (p + filesize + 3) & ~3
        if nm == 'TRAILER!!!': break
        yield nm, f[1], data  # name, mode, data
total = 0
for rn, ro, rs, rt in entries:
    blob = ramdisk[ro:ro+rs]
    raw = decompress(blob)
    print(f'ramdisk {rn!r} type {rt}: {rs} -> {len(raw)} bytes')
    for nm, mode, data in walk_cpio(raw):
        if nm.endswith('.ko') or os.path.basename(nm).startswith('modules.'):
            dst = os.path.join(out, rn.replace('/', '_') or 'ramdisk', nm)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, 'wb').write(data); total += 1
print('extracted', total, 'files')
