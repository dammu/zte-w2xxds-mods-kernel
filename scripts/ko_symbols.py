#!/usr/bin/env python3
"""Collect imported symbol CRCs (__versions), exported CRCs (__ksymtab/__kcrctab via .modinfo not needed),
vermagic and signer info from a set of OEM .ko files. Pure stdlib.
Usage: ko_symbols.py <out.json> <dir-or-ko>..."""
import sys, os, struct, json
def parse(path):
    d = open(path, 'rb').read()
    shoff = struct.unpack_from('<Q', d, 0x28)[0]; shentsize, shnum, shstrndx = struct.unpack_from('<HHH', d, 0x3a)
    secs = [struct.unpack_from('<IIQQQQIIQQ', d, shoff + i*shentsize) for i in range(shnum)]
    stroff = secs[shstrndx][4]
    def nm(n): e = d.index(b'\0', stroff + n); return d[stroff+n:e].decode()
    names = {nm(s[0]): s for s in secs}
    r = {'imports': {}, 'exports': [], 'vermagic': None, 'signed': d.endswith(b'~Module signature appended~\n')}
    if '__versions' in names:
        s = names['__versions']; off, size = s[4], s[5]
        for j in range(size // 64):
            crc = struct.unpack_from('<Q', d, off + j*64)[0]
            sym = d[off+j*64+8:off+j*64+64].split(b'\0')[0].decode()
            r['imports'][sym] = crc & 0xffffffff
    if '.modinfo' in names:
        s = names['.modinfo']; info = d[s[4]:s[4]+s[5]].split(b'\0')
        for x in info:
            if x.startswith(b'vermagic='): r['vermagic'] = x[9:].decode()
            if x.startswith(b'name='): r['name'] = x[5:].decode()
    # exported symbols: names in __ksymtab_strings referenced by __ksymtab*; simpler: symtab GLOBAL defined in __ksymtab sections is complex;
    # use strings from __ksymtab_strings section (NUL separated) as the export list.
    if '__ksymtab_strings' in names:
        s = names['__ksymtab_strings']; r['exports'] = [x.decode() for x in d[s[4]:s[4]+s[5]].split(b'\0') if x]
    return r
out = sys.argv[1]; files = []
for a in sys.argv[2:]:
    if os.path.isdir(a):
        for root, _, fs in os.walk(a):
            files += [os.path.join(root, f) for f in fs if f.endswith('.ko')]
    else: files.append(a)
mods = {}; allimp = {}; conflicts = []
for f in sorted(files):
    r = parse(f); key = os.path.basename(f)
    mods[key] = {'source': 'vendor_boot ramdisk' if 'vendor_boot' in f.replace(chr(92), '/') else '/vendor/lib/modules', **r}
    for s, c in r['imports'].items():
        if s in allimp and allimp[s] != c: conflicts.append((s, key, allimp[s], c))
        allimp[s] = c
json.dump({'modules': mods, 'imports': allimp, 'conflicts': conflicts}, open(out, 'w'), indent=1, sort_keys=True)
print(f'{len(mods)} modules, {len(allimp)} distinct imported symbols, {len(conflicts)} conflicts, module_layout=0x{allimp.get("module_layout",0):08x}')
vm = {m['vermagic'] for m in mods.values()}; print('vermagic:', vm)
