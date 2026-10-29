# BUILDING — 从零到可刷的 boot 镜像

## 0. 需要准备的东西（都不在仓库里）

| 项目 | 来源 |
| --- | --- |
| 原厂 `boot_a` 镜像（64 MiB 分区 dump，带 AVB footer） | 自己从设备备份（BROM `spd_dump` 读 `boot_a`，或解锁前的全分区备份） |
| 原厂 `vendor_boot_a` 镜像 | 同上；用来解出 ramdisk 里的 167 个 .ko 做 ABI 表 |
| 设备 `/vendor/lib/modules/*.ko`（147 个） | root 下复制出来 |
| 设备 `/proc/config.gz` | `adb exec-out "zcat /proc/config.gz"`（仓库 `configs/` 里有 20251013 固件的一份） |
| 设备 `/system/etc/vintf/compatibility_matrix.*.xml` | root 下 `cat` 出来放到 `vintf/`；VINTF 门禁的输入，不随仓库分发 |
| ZTE 开源内核树 | `Ssrml/android_kernel_zte_ums9620_p720_w205ds`（GitHub tarball） |
| BakaSU 上游 | `Baka-SU/BakaSU` main |
| SUSFS 2.3.0 的 5.4 回移 | `kafuuchino-s/susfs4ksu` 分支 `mix4-5.4`，`patches/5.4/2.3.0/`（本仓库的 0002 补丁已包含应用结果） |
| Droidspaces kABI 补丁 | `ravindu644/Droidspaces-OSS`，`Documentation/resources/kernel-patches/GKI/below-kernel-6.12/`（本仓库 0005 已包含） |
| 工具链 | Android clang `r416183b`（`platform/prebuilts/clang/host/linux-x86`，`android12-release` 分支） |

构建机：Ubuntu 22.04/24.04，**至少 36 GB 内存**（Full LTO 链接 vmlinux 时 `ld.lld` 常驻 24 GB 以上，24 GB 的机器会被 OOM 杀），150 GB 磁盘，12 核左右。全量编译约 35 分钟 + 链接 10 分钟；增量（只改 kernelsu 目录或配置）15–20 分钟。

## 1. 环境

`scripts/vm-setup.sh` 做：apt 依赖、下载解压 clang、clone 小仓库（BakaSU、susfs4ksu、Droidspaces、odin 的工具目录）。两棵大内核树在虚拟机里 clone 容易失败/极慢，`scripts/vm-fetch-sources.sh` 改用 GitHub tarball，或在主机下载后 scp 进去。

脚本假定的布局（VM 内）：

```
~/kb/toolchain/clang-r416183b/
~/kb/src/zte-w205ds        ZTE 开源树（建议 git init 做基线提交）
~/kb/src/bakasu-upstream   Baka-SU/BakaSU main
~/kb/src/susfs4ksu-mix4    kafuuchino-s/susfs4ksu mix4-5.4
~/kb/src/droidspaces
~/kb/w203ds/host-tools/    = 本仓库 scripts/
~/kb/w203ds/stock/         config-running.txt、zte-oem-module.x509.pem、builtin-fw/
~/kb/w203ds/oem-modules/   oem-symbols.json
~/kb/w203ds/vintf/         从设备拉的 /system/etc/vintf/compatibility_matrix.*.xml（不在仓库里）
~/kb/out/baseline-ssrml    输出目录（所有阶段共用，增量）
```

## 2. 准备源码树

1. 解出原厂材料：
   - `scripts/bootinfo.py boot_a.img` 看布局；
   - `scripts/extract_oem_cert.py boot_a.img zte-oem-module.x509.der zte-oem-module.x509.pem`；
   - `scripts/carve_builtin_fw.py <Image> builtin-fw/` 得到 5 个触摸固件，放到 `drivers/vendor/common/firmware/`；
   - `drivers/vendor/common/touchscreen_v2/focaltech_touch_pad/include/firmware/fw_sample.i` 建一个空文件。
2. 原厂 config 原样复制为 `arch/arm64/configs/w203ds_defconfig`（不要 `savedefconfig` 压缩），`.scmversion` 写 `-android12-9-gb4a927d994a0`，证书复制到 `certs/`。
3. `git init` 并提交这个基线。
4. 打补丁：`git am patches/zte-5.4.276-bakasu-susfs-droidspaces/*.patch`。其中 0001 建 `drivers/kernelsu -> ../../bakasu-upstream/kernel` 软链并接入 `drivers/Kconfig`、`drivers/Makefile`，所以 `~/kb/src/bakasu-upstream` 要先在。

## 3. ABI 表

```
scripts/extract_vendor_boot_modules.py vendor_boot_a.bin oem-modules/vendor_boot   # 需要 lz4 模块；uv run --python 3.12
scripts/ko_symbols.py oem-modules/oem-symbols.json <vendor-lib-modules 目录> oem-modules/vendor_boot
```

得到 205 个模块的引用符号与 CRC（仓库 `abi/oem-symbols-20251013.json` 是 20251013 固件的结果，换固件要重做）。

## 4. 编译与门禁

先跑一次纯净基线确认源码树对得上本机固件：

```
scripts/vm-build-baseline.sh      # 原厂 config，不含 KSU；结束时打印 ABI 审计
```

通过标准：`MISMATCH: 0  MISSING: 0`，`module_layout` 两边相同。如果不闭合，先别往下做。

现行配方：

```
scripts/vm-build-p4b.sh           # defconfig = 原厂 config + configs/fragments/ksu-susfs-droidspaces.fragment
```

脚本顺序：生成 defconfig → `olddefconfig` → `diffconfig` 打印相对原厂的全部漂移（逐项看，不该变的不能变）→ **VINTF 门禁**（`audit_vintf_kernel.py … 5.4.276 6 …`，失败即停）→ `make Image modules` → 打印 BakaSU 自检行、`uname` 串 → ABI 审计。

其它片段：`ksu-manual-hook.fragment`（无 SUSFS，配 `patches/alt-manual-hook/`）、`ksu-susfs.fragment`（P3，不含 Droidspaces 选项）。

## 5. 打包

```
scripts/pack_boot.py <原厂 boot_a.img> out/arch/arm64/boot/Image boot_a-new.img
```

只替换 kernel，断言 ramdisk 逐字节不变、vbmeta 块原样后移、footer 偏移更新、总长仍 64 MiB，并打印 sha256。

## 6. 升级流程（上游 BakaSU / SUSFS 有新版本时）

1. VM 里 `git -C ~/kb/src/bakasu-upstream pull`（或切到目标 tag）。BakaSU 的 Kbuild 会自动 `git fetch --unshallow` 来算版本码，浅克隆第一次评估会得到错误的版本码。
2. SUSFS 有新版本时，用新的 5.4 回移替换 0002 补丁的内容，再看 0003/0004 两处契约适配是否仍需要（看上游 `feature/sucompat.h`、`tools/inline_hook_check.mk`）。
3. 跑 `scripts/vm-build-p4b.sh`，三道门（diffconfig、VINTF、ABI）都过再打包。
4. 管理器也要换成同一版本（uapi 相同），见 FLASHING.md。
5. 按 FLASHING.md 刷写验收。

## 7. 已知的坑

- `KBUILD_BUILD_TIMESTAMP` 带空格和冒号，要 `export`，不能放在 make 参数串里展开（会报 `target pattern contains no '%'`）。
- 不要把 `*.pem` 之外的 `certs/` 内容（自动生成的 `signing_key.pem`）提交进来。
- ACK 5.4.276 与 kafuuchino 的宿主（高通 5.4.259）差异导致 4 个 hunk 失败：`fs/proc/fd.c`（多打印 `ino:`）、`fs/proc/task_mmu.c`（两处 `smap_gather_stats` + `show_smap_vma` 是 void）、`security/selinux/avc.c`（用 `tcontext` 变量和 `trace_selinux_audited`）。0002 补丁里是合并好的结果，换 SUSFS 版本时这几处要重新对。
