#!/usr/bin/env python3
"""Print the layout of Android boot image v3/v4 dumps (header fields, kernel compression, AVB footer)."""
import hashlib, struct, sys
for p in sys.argv[1:]:
    d = open(p, 'rb').read(); print('==', p, len(d), 'bytes')
    if d[:8] != b'ANDROID!': print('  not a boot image'); continue
    ks, rs, osv, hs = struct.unpack_from('<IIII', d, 8); hv = struct.unpack_from('<I', d, 40)[0]
    page = 4096; koff = page; roff = koff + (ks + page - 1)//page*page; pend = roff + (rs + page - 1)//page*page
    maj, mi, pa = (osv >> 25) & 0x7f, (osv >> 18) & 0x7f, (osv >> 11) & 0x7f; y, mo = ((osv >> 4) & 0x7f) + 2000, osv & 0xf
    k = d[koff:koff+ks]
    kind = 'gzip' if k[:2] == b'\x1f\x8b' else 'lz4' if k[:4] == b'\x04\x22\x4d\x18' else 'raw arm64 Image' if k[56:60] == b'ARM\x64' else 'unknown'
    print(f'  header v{hv} kernel {ks} ({kind}) ramdisk {rs} os {maj}.{mi}.{pa} patch {y:04d}-{mo:02d} payload_end {pend:#x}')
    print('  kernel sha256', hashlib.sha256(k).hexdigest(), '| ramdisk sha256', hashlib.sha256(d[roff:roff+rs]).hexdigest()[:16])
    f = d[-64:]
    if f[:4] == b'AVBf':
        osz, voff, vsz = struct.unpack_from('>QQQ', f, 12); print(f'  AVB footer: original_image_size {osz:#x} vbmeta_offset {voff:#x} vbmeta_size {vsz}')
