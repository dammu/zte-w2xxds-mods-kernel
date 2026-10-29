#!/bin/bash
# P4b: P4 minus SYSVIPC and IP6_NF_NAT (forbidden by the Android 13 VINTF compatibility matrix).
set -o pipefail; cd ~/kb
SRC=${SRC:-~/kb/src/zte-w205ds}; OUT=${OUT:-~/kb/out/baseline-ssrml}; FRAG=${FRAG:-~/kb/w203ds/host-tools/ksu-p4b.fragment}
export PATH=~/kb/toolchain/clang-r416183b/bin:$PATH
grep -v '^CONFIG_SYSTEM_TRUSTED_KEYS=' ~/kb/w203ds/stock/config-running.txt > $SRC/arch/arm64/configs/w203ds_defconfig
cat $FRAG >> $SRC/arch/arm64/configs/w203ds_defconfig
printf -- '-android12-9-gb4a927d994a0' > $SRC/.scmversion
MK="make -C $SRC O=$OUT ARCH=arm64 LLVM=1 LLVM_IAS=1 CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_COMPAT=arm-linux-androidkernel- KBUILD_BUILD_USER=zte KBUILD_BUILD_HOST=ironic-r5300-b0113-04"
export KBUILD_BUILD_TIMESTAMP="Mon Oct 13 22:29:43 CST 2025" KBUILD_BUILD_VERSION=1
echo "== defconfig"; $MK w203ds_defconfig 2>&1 | grep -vE "^make|^#$" | tail -5
echo "== KSU options in .config"; grep -E "^(# )?CONFIG_(KSU|KSU_SUSFS)" $OUT/.config
echo "== config drift (running -> build)"; $SRC/scripts/diffconfig ~/kb/w203ds/stock/config-running.txt $OUT/.config | grep -v 'CC_VERSION_TEXT'
echo "== VINTF kernel-requirement gate (compatibility_matrix level 6 governs this 5.4 kernel)"
python3 ~/kb/w203ds/host-tools/audit_vintf_kernel.py $OUT/.config 5.4.276 6 ~/kb/w203ds/vintf/compatibility_matrix.*.xml || { echo "VINTF GATE FAILED - system_server would show the internal-problem dialog"; echo "BUILD DONE rc=99"; exit 99; }
echo "== build start $(date -Is)"
( time $MK -j${JOBS:-12} Image modules ) > $OUT/build.log 2>&1; rc=$?
echo "== build end $(date -Is) rc=$rc"
grep -nE "fatal error|error:|Error [0-9]|undefined|No rule|manual_hook|You lost|You should" $OUT/build.log | head -40
tail -3 $OUT/build.log
ls -la $OUT/arch/arm64/boot/Image $OUT/Module.symvers 2>&1
grep -a -m1 -o "Linux version [^(]*([^)]*) ([^)]*)" $OUT/vmlinux 2>/dev/null
echo "== KSU symbols in vmlinux: $(grep -c " ksu_" $OUT/System.map)"; grep -E " (ksu_handle_execveat|ksu_handle_stat|ksu_handle_faccessat|ksu_handle_sys_reboot|ksu_handle_vfs_fstat)$" $OUT/System.map
echo "== ABI audit"; python3 ~/kb/w203ds/host-tools/audit_abi.py $OUT/Module.symvers ~/kb/w203ds/oem-modules/oem-symbols.json --report $OUT/abi-report.json
echo "BUILD DONE rc=$rc"
