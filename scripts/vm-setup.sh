#!/bin/bash
# One-time VM setup: wait for cloud-init, fetch toolchain and sources. Logs to ~/kb/setup.log
set -o pipefail
mkdir -p ~/kb/src ~/kb/toolchain; cd ~/kb
echo "[$(date -Is)] waiting for cloud-init"; cloud-init status --wait >/dev/null 2>&1 || true; cloud-init status
sudo apt-get install -y -q build-essential bc bison flex libssl-dev libelf-dev python3 git lz4 cpio rsync curl wget unzip zstd ccache binutils-aarch64-linux-gnu open-vm-tools 2>&1 | tail -2
echo "[$(date -Is)] toolchain"; cd ~/kb/toolchain
if [ ! -x clang-r416183b/bin/clang ]; then
  curl -L --retry 5 -o clang-r416183b.tgz "https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86/+archive/refs/heads/android12-release/clang-r416183b.tar.gz"
  mkdir -p clang-r416183b && tar xzf clang-r416183b.tgz -C clang-r416183b && rm -f clang-r416183b.tgz
fi
clang-r416183b/bin/clang --version | head -1
echo "[$(date -Is)] sources"; cd ~/kb/src
c() { d=$1; shift; [ -d "$d" ] || git clone --depth=1 "$@" "$d" 2>&1 | tail -1; }
c zte-w205ds https://github.com/Ssrml/android_kernel_zte_ums9620_p720_w205ds.git
c w200ds https://github.com/WiteTanuki/W200DS-SukiSU-Kernel.git
c bakasu-mix4 --branch mix4-5.4 https://github.com/kafuuchino-s/BakaSU.git
c susfs4ksu-mix4 --branch mix4-5.4 https://github.com/kafuuchino-s/susfs4ksu.git
c bakasu-upstream https://github.com/Baka-SU/BakaSU.git
c droidspaces https://github.com/ravindu644/Droidspaces-OSS.git
if [ ! -d odin ]; then git clone --depth=1 --filter=blob:none --sparse --branch mix4-5.4 https://github.com/kafuuchino-s/kernel_xiaomi_odin.git odin 2>&1 | tail -1 && (cd odin && git sparse-checkout set tools/mix4 kernel-patches configs INTEGRATION.md build.sh README.md 2>&1 | tail -1); fi
du -sh ~/kb/src/* ~/kb/toolchain/* 2>/dev/null
echo "[$(date -Is)] SETUP DONE"
