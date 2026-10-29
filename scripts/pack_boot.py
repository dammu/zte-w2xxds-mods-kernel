#!/usr/bin/env python3
"""Replace only the kernel inside an Android boot image v3/v4 partition dump (64 MiB, with AVB footer),
mirroring what magiskboot repack does for AVB-footered images: header/ramdisk/vbmeta blob are copied
byte-for-byte, kernel_size is updated, the vbmeta blob is re-appended right after the payload and the
AVB footer's original_image_size/vbmeta_offset are updated (the vbmeta digest is left stale, which an
unlocked bootloader tolerates - same as the APatch image that boots today).
Usage: pack_boot.py <stock_boot.bin> <new_Image> <out.img>"""
import sys, struct, hashlib
stock, newk, out = sys.argv[1:4]
d = open(stock, 'rb').read(); k = open(newk, 'rb').read()
assert d[:8] == b'ANDROID!' and k[56:60] == b'ARM\x64', 'bad inputs'
hv = struct.unpack_from('<I', d, 40)[0]; assert hv in (3, 4), hv
page = 4096; ks, rs = struct.unpack_from('<II', d, 8)
koff = page; roff = koff + (ks + page - 1)//page*page; pend = roff + (rs + page - 1)//page*page
foot = d[-64:]; assert foot[:4] == b'AVBf', 'no AVB footer'
osz, voff, vsz = struct.unpack_from('>QQQ', foot, 12)
assert osz == pend == voff, (hex(osz), hex(pend), hex(voff))
vb = d[voff:voff+vsz]; assert vb[:4] == b'AVB0'
hdr = bytearray(d[:page]); struct.pack_into('<I', hdr, 8, len(k))
rd = d[roff:roff+rs]
pad = lambda b: b + b'\0' * ((-len(b)) % page)
body = bytes(hdr) + pad(k) + pad(rd)
newpend = len(body)
img = bytearray(body + vb)
img += b'\0' * (len(d) - len(img))
nf = bytearray(foot); struct.pack_into('>QQ', nf, 12, newpend, newpend)
img[-64:] = nf
assert len(img) == len(d)
open(out, 'wb').write(img)
print(f'kernel {ks} -> {len(k)} bytes; payload end {pend:#x} -> {newpend:#x}; ramdisk sha256 {hashlib.sha256(rd).hexdigest()[:16]} unchanged; out sha256 {hashlib.sha256(img).hexdigest()}')
