# UPDATING — 跟进上游更新的流程

内核里的 BakaSU 和 SUSFS 都是编进去的，所以**任何内核侧更新都要重编一次、重刷一次 `boot_a`**。用户态（管理器 app、ksud、元模块、Zygisk 等）可以单独升级，但管理器与内核的 uapi 版本必须一致。

本文假定构建环境已按 [BUILDING.md](BUILDING.md) 搭好，源码树在 `~/kb/src/zte-w205ds`，当前补丁已经应用、有 git 历史。

## 0. 先判断属于哪一种更新

| 变化 | 要做什么 | 章节 |
| --- | --- | --- |
| BakaSU 出了新 tag（内核侧 `kernel/` 有改动） | 更新 BakaSU 源码，重编，换同版本管理器 | §1 |
| 只有管理器 / ksud 更新，uapi 不变 | 直接装新 APK，不碰内核 | §1.4 |
| SUSFS 出新版本 | 更新内核侧补丁（可能要重做 5.4 回移），重编；ksud 自带的 SUSFS 用户态随 BakaSU 走 | §2 |
| Droidspaces 新版本 | 一般只装 app；它的内核要求变了才重编 | §3 |
| ZTE 推了新固件（OTA） | 全部重来：新基线、重做 ABI 表、重新验证 | §4 |
| 想开/关某个内核选项 | 改配置片段，过 VINTF 和 ABI 门禁 | §5 |

每种情况结束前都要走 §6 的门禁和 [FLASHING.md](FLASHING.md) 的验收。

## 1. BakaSU 上游更新

1. 看上游 release notes，重点三项：`KERNEL_SU_UAPI_VERSION` 是否变（`kernel/include/uapi/supercall.h`）；`tools/inline_hook_check.mk`（SUSFS 模式）或 `tools/manual_hook_check.mk` 里要求的 `ksu_handle_*` 名字和文件是否变；`feature/sucompat.h` 里 hook 函数的签名是否变。
2. 更新源码：
   ```
   cd ~/kb/src/bakasu-upstream && git fetch --tags && git checkout <tag>
   ```
   `drivers/kernelsu` 是指向它的软链，内核树本身不用动。BakaSU 的 Kbuild 用 `git rev-list --count` 算版本码，必须是完整克隆（浅克隆它会自己 `fetch --unshallow`，第一次评估的版本码会错）。
3. 如果第 1 步发现 hook 契约变了，改内核树里的调用点并把改动追加成新的补丁（`git format-patch`），更新本仓库 `patches/`。已经遇到过的两种变化：`ksu_handle_sys_read` 从 1 参数变 3 参数；`ksu_handle_post_execve` 被 `ksu_handle_post_execveat` 取代。
4. 管理器：BakaSU 管理器只在 CI 产物里（nightly.link 的 `Manager-release.zip` 或某次 workflow run 的 artifact）。取**和内核同一提交**的构建；`apksigner verify --print-certs` 确认签名证书 sha256 是内核 `manager/manager_sign.h` 里的那把（PR 构建用别的证书，内核不认）。先编内核、后装管理器；版本码/uapi 显示为 `35252/6` 这类，两边要一样。
5. 重编：`scripts/vm-build-p4b.sh`（kernelsu 目录对象会因 flags 变化自动重编），然后 §6。

## 2. SUSFS 更新

SUSFS 官方只维护 5.10+ 的 GKI 分支，5.4 是回移的，所以这是最花时间的一种更新。

1. 看 SUSFS 更新日志和 BakaSU 的要求（BakaSU 明确说只跟 simonpunk 最新内核侧，不保证向后兼容）。
2. 来源二选一：
   - kafuuchino-s/susfs4ksu 的 `mix4-5.4` 分支如果已经回移了新版本，直接取 `patches/5.4/<version>/` 的系列；
   - 否则拿上游 `gki-android12-5.10` 分支的 `50_add_susfs_in_kernel-5.10.patch` 和 `kernel_patches/{fs,include}` 自己回移到 5.4。
3. 在内核树上先 `git reset` 到 0001（接入 BakaSU）之后、0002 之前的状态，应用新的 SUSFS 系列，逐个处理失败的 hunk。ACK 5.4.276 上已知要手工对的位置：`fs/proc/fd.c` 的 `seq_show`（ACK 多打印 `ino:`）、`fs/proc/task_mmu.c` 的 `show_smaps_rollup`（两处 `smap_gather_stats`）和 `show_smap_vma`（void 函数）、`security/selinux/avc.c` 的 `avc_audit_post_callback`（用 `tcontext` 和 `trace_selinux_audited`）。W200DS 工程的 2.2.0 集成是另一份 5.4 参照。
4. 重新对一遍 BakaSU 的契约（§1 第 1 步），因为 SUSFS 系列自带的是它那个时间点的 `ksu_handle_*` 调用。
5. 重新生成 0002–0004 补丁，更新本仓库 `patches/`，然后 §6。
6. 刷入后 `ksud susfs show version` 应显示新版本；SUSFS 持久化配置在 `/data/adb/ksu/.susfs.json`，升级不会丢，但新版本的新开关需要自己决定开不开。

## 3. Droidspaces 更新

- 通常只需要在设备上升级 app（它会自己更新 `/data/adb/modules/droidspaces` 和 `/data/local/Droidspaces/bin`）。
- 升级后跑一次 `droidspaces check`。它的 `Documentation/Kernel-Configuration.md` 里"必需"列表变了才需要动内核：新选项先过 §5 的流程；它的 kABI 补丁有版本（`below-kernel-6.12/001.*_6_7_8` 等），如果换了槽位要确认不和 SUSFS 用到的 `ANDROID_KABI_USE` 槽位冲突（当前 SUSFS 2.3.0 不占 `task_struct` 槽位）。

## 4. ZTE 新固件

新固件意味着新的原厂内核和新的预编译模块，之前的一切假设都要重验：

1. 刷新固件前先备份新旧 `boot_a`；刷完固件后用 `adb exec-out "zcat /proc/config.gz"` 取新配置，核对 `uname -a` 的版本串、构建时间（`KBUILD_BUILD_TIMESTAMP`、`.scmversion` 都要改成新值）。
2. 重新复制 `/vendor/lib/modules` 和解出 `vendor_boot` 的模块，重做 `abi/oem-symbols-*.json`。
3. 重新从新 Image 提取证书（可能没变）和内置固件。
4. 如果 ZTE 更新了开源 drop，换新树；否则用旧树 + 新配置先跑 `scripts/vm-build-baseline.sh`，看 ABI 是否仍闭合。不闭合说明源码不匹配，不要往下做。
5. 重新拉 `/system/etc/vintf/compatibility_matrix.*.xml`（level 可能变）。
6. 之后按 BUILDING.md 走完整流程。

## 5. 改内核选项

1. 改 `configs/fragments/*.fragment`（或新建一个片段，用 `FRAG=` 传给构建脚本）。
2. 看构建日志里 `diffconfig` 打印的漂移，确认只有你想改的以及它们 `select` 出来的东西。
3. VINTF 门禁：矩阵要求为 `n` 的选项不能开（`scripts/audit_vintf_kernel.py <.config> 5.4.276 6 <矩阵…>`）。
4. ABI 门禁：改结构体布局的选项（例如 `CGROUP_PIDS`，或 `SYSVIPC`、`CFS_BANDWIDTH` 不带对应补丁时）会让审计出现 MISMATCH，不能刷。先在 VM 里只编对象（`make <vmlinux-dirs>`，不做 LTO 链接，约 2 分钟）、收集 `*.o.symversions` 喂 `audit_abi.py`，就能知道哪些符号变、能不能用 kABI 槽位或 `__GENKSYMS__` 遮掉，再决定要不要全量构建。
5. 过了再刷，刷后跑 `postcheck.sh` 并看开机有没有弹窗。

## 6. 每次都要过的门禁（顺序）

1. `diffconfig` 漂移逐项可解释。
2. VINTF 内核要求审计 0 违规（构建脚本内置，失败即停）。
3. ABI 审计 `MISMATCH: 0 MISSING: 0`，`module_layout` 不变。
4. `pack_boot.py` 校验通过（ramdisk 逐字节不变，64 MiB）。
5. 管理器版本与内核 uapi 一致。
6. 按 FLASHING.md：只写 `boot_a`，刷后 `postcheck.sh`，看 dmesg 错误、tombstone、HAL 重启、enforcing 拒绝、弹窗。

## 7. 版本记录

把每次刷过的组合记在一处（内核 tag/提交、BakaSU 提交、SUSFS 版本、配置片段、boot 镜像 sha256、刷写日期、结果）。本仓库的 [DESIGN.md](DESIGN.md) 阶段表和发布记录就是这样的记录，每刷一版追加一行。

## 8. 发布到 GitHub Releases

只发布**已经在设备上刷过并通过 FLASHING.md 验收**的构建，流程：

1. 从构建目录取 `boot_a-*.img`、`Image`、`.config`，加上配套的管理器 APK（`apksigner verify --print-certs` 核对签名是 `manager_sign.h` 里的证书），按 `<类型>-w203ds-<固件>-bakasu<版本码>-susfs<版本>-<阶段>` 命名，`sha256sum * > SHA256SUMS`。
2. 先提交文档：DESIGN.md 的阶段表 / 发布记录追加一行，README 的下载表若字段有变也改。
3. `gh release create <tag> <文件…> --title … --notes-file …`，tag 用 `v<YYYYMMDD>-<阶段>`，打在刚提交的 commit 上。说明里写清：固件、BakaSU 版本码/uapi 与提交、SUSFS 版本、关掉的选项、验证过与没验证的、回退方法。
4. 发布后 `gh release view <tag>` 核对资产数量和大小，再用 `gh release download` 抽一个文件比对 sha256。
