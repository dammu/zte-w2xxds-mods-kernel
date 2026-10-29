#!/bin/bash
# P1: build a pristine kernel from the ZTE W205DS drop with the W203DS running config, then audit OEM module CRCs.
set -o pipefail
cd ~/kb
until grep -q "SETUP DONE" ~/kb/setup.log 2>/dev/null; do sleep 20; done
SRC=${SRC:-~/kb/src/zte-w205ds}; OUT=${OUT:-~/kb/out/baseline-ssrml}; mkdir -p $OUT
export PATH=~/kb/toolchain/clang-r416183b/bin:$PATH
cp ~/kb/w203ds/stock/config-running.txt $SRC/arch/arm64/configs/w203ds_defconfig
printf -- '-android12-9-gb4a927d994a0' > $SRC/.scmversion
cp ~/kb/w203ds/stock/zte-oem-module.x509.pem $SRC/certs/
sed -i 's|^CONFIG_SYSTEM_TRUSTED_KEYS=.*|CONFIG_SYSTEM_TRUSTED_KEYS="certs/zte-oem-module.x509.pem"|' $SRC/arch/arm64/configs/w203ds_defconfig
echo "== config keys"; grep -E '^CONFIG_(SYSTEM_TRUSTED_KEYS|MODULE_SIG_KEY|LOCALVERSION)' $SRC/arch/arm64/configs/w203ds_defconfig
MK="make -C $SRC O=$OUT ARCH=arm64 LLVM=1 LLVM_IAS=1 CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_COMPAT=arm-linux-androidkernel- KBUILD_BUILD_USER=zte KBUILD_BUILD_HOST=ironic-r5300-b0113-04"
echo "== defconfig"; $MK w203ds_defconfig 2>&1 | tail -3
echo "== config drift (running -> build)"; $SRC/scripts/diffconfig ~/kb/w203ds/stock/config-running.txt $OUT/.config | grep -v 'CC_VERSION_TEXT' | head -60
echo "== build start $(date -Is)"
( time $MK -j${JOBS:-12} Image modules ) > $OUT/build.log 2>&1; rc=$?
echo "== build end $(date -Is) rc=$rc"
grep -nE "error:|Error [0-9]|undefined reference|No rule to make" $OUT/build.log | head -30
tail -3 $OUT/build.log
ls -la $OUT/arch/arm64/boot/Image $OUT/Module.symvers 2>&1
$MK -s kernelrelease 2>/dev/null | tail -1
grep -a -m1 -o "Linux version [^(]*([^)]*) ([^)]*)" $OUT/vmlinux 2>/dev/null
find $OUT -name '*.ko' | wc -l
echo "== ABI audit"; python3 ~/kb/w203ds/host-tools/audit_abi.py $OUT/Module.symvers ~/kb/w203ds/oem-modules/oem-symbols.json --report $OUT/abi-report.json
echo "BUILD DONE rc=$rc"
