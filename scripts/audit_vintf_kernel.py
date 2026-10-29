#!/usr/bin/env python3
"""Check a kernel .config against the kernel <config> requirements of Android framework compatibility
matrices (what system_server's Build.isBuildConsistent()/VINTF runtime check enforces).
Usage: audit_vintf_kernel.py <config> <kernel-version e.g. 5.4.276> <target-level> <matrix.xml>..."""
import sys, re, xml.etree.ElementTree as ET
cfg_path, kver, level = sys.argv[1], sys.argv[2], int(sys.argv[3]); mats = sys.argv[4:]
cfg = {}
for l in open(cfg_path, encoding='utf-8', errors='replace'):
    m = re.match(r'^(CONFIG_\w+)=(.*)$', l.strip())
    if m: cfg[m.group(1)] = m.group(2); continue
    m = re.match(r'^# (CONFIG_\w+) is not set', l.strip())
    if m: cfg[m.group(1)] = 'n'
kmaj, kmin, kpatch = (int(x) for x in kver.split('.')[:3])
def ver_ok(v):
    a = [int(x) for x in v.split('.')]
    return a[0] == kmaj and a[1] == kmin and kpatch >= a[2]
viol = []; checked = 0; blocks = 0
for mp in mats:
    root = ET.parse(mp).getroot()
    for k in root.findall('kernel'):
        v = k.get('version'); lv = int(k.get('level', '0') or 0)
        if not ver_ok(v) or lv != level: continue
        conds = k.findall('conditions/config')
        cond_ok = all(cfg.get(c.find('key').text, 'n') == c.find('value').text for c in conds)
        if not cond_ok: continue
        blocks += 1
        for c in k.findall('config'):
            key, val = c.find('key').text, c.find('value').text; typ = c.find('value').get('type'); checked += 1
            have = cfg.get(key, 'n' if typ == 'tristate' else None)
            if typ == 'tristate':
                if val == 'n' and have != 'n': viol.append((mp, key, val, have))
                if val == 'y' and have != 'y': viol.append((mp, key, val, have))
                if val == 'm' and have not in ('m', 'y'): viol.append((mp, key, val, have))
            elif typ == 'string':
                if (have or '').strip('"') != val: viol.append((mp, key, val, have))
            else:
                if have is None or str(have).strip('"') != str(val): viol.append((mp, key, val, have))
print(f'kernel {kver} level {level}: matched {blocks} requirement block(s), checked {checked} configs, violations {len(viol)}')
for mp, key, val, have in viol: print(f'  VIOLATION {key}: required {val}, have {have}  ({mp.split("/")[-1]})')
sys.exit(1 if viol else 0)
