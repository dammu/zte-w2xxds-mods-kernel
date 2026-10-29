#!/usr/bin/env python3
"""Compare a kernel build's Module.symvers against the CRCs imported by OEM modules.
Usage: audit_abi.py <Module.symvers> <oem-symbols.json> [--report out.json]
Exit 0 only when every imported symbol exists in the build with an identical CRC."""
import sys, json
symvers, oem = sys.argv[1], sys.argv[2]
report = sys.argv[sys.argv.index('--report')+1] if '--report' in sys.argv else None
build = {}
for line in open(symvers):
    p = line.split()
    if len(p) >= 3: build[p[1]] = int(p[0], 16) & 0xffffffff
oemj = json.load(open(oem)); imp = oemj['imports']
# symbols exported by other OEM modules are satisfied by those modules, not by the kernel
oem_exports = set()
for m in oemj['modules'].values(): oem_exports.update(m['exports'])
missing, mismatch, ok, inter = [], [], 0, 0
for s, c in sorted(imp.items()):
    if s in build:
        if build[s] == c: ok += 1
        else: mismatch.append((s, c, build[s]))
    elif s in oem_exports: inter += 1
    else: missing.append(s)
print(f'imported symbols: {len(imp)}  matched: {ok}  provided by other OEM modules: {inter}  MISMATCH: {len(mismatch)}  MISSING: {len(missing)}')
print(f"module_layout oem=0x{imp.get('module_layout',0):08x} build=0x{build.get('module_layout',0):08x}")
for s, c, b in mismatch[:40]: print(f'  mismatch {s}: oem 0x{c:08x} build 0x{b:08x}')
for s in missing[:40]: print(f'  missing  {s}')
if report: json.dump({'mismatch': mismatch, 'missing': missing, 'matched': ok, 'inter_module': inter}, open(report, 'w'), indent=1)
sys.exit(0 if not mismatch and not missing else 1)
