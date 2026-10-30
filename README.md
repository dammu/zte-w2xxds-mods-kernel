# zte-w2xxds-mods-kernel

A rebuildable Linux 5.4.276 kernel for the ZTE W2xxDS "cloud PC" tablet (Unisoc T760 / ums9620, Android 13) that adds **BakaSU** (a KernelSU fork, built in), **SUSFS 2.3.0** and the kernel options **Droidspaces** containers need, while keeping every prebuilt vendor module loading and reporting the same `uname -a` as the stock kernel.

This repository is primarily the recipe: patches against ZTE's open-source kernel drop, config fragments, build/audit/packing scripts and documentation. A build that has been flashed and tested on the author's device is attached to [Releases](https://github.com/dammu/zte-w2xxds-mods-kernel/releases). **Only the W203DS on firmware 20251013 has been tested.**

---

## 背景

W2xxDS 是中兴面向运营商"云电脑"场景的平板（W200 公开版、W201 电信、W202 移动、W203、W205 eSIM 等后缀对应不同运营商），紫光展锐 T760，Android 13，内核 5.4.276。它可以通过展讯公钥签名的方式解锁 BL，社区常用 APatch 取得 root。

做这个项目的原因有三个：

1. 原厂内核没有 PID / IPC 命名空间等选项，Droidspaces 这类容器方案跑不起来；
2. 想从 APatch 迁到 KernelSU 系（BakaSU）并带上 SUSFS；
3. 这两件事都只能靠自己编内核，而这台机器的内核坏了只能靠 BROM 深刷救回，所以需要一套"编之前就能确定能开机"的方法。

核心方法来自 [W200DS-SukiSU-Kernel](https://github.com/WiteTanuki/W200DS-SukiSU-Kernel)：用 ZTE 开源树 + 本机 `/proc/config.gz` 重编，把原厂模块签名证书放进 `SYSTEM_TRUSTED_KEYS`，并逐一核对原厂 205 个预编译模块引用的全部符号 CRC（`MODVERSIONS`），闭合了才刷。在此基础上本项目加了第二道门禁：按 system_server 的 VINTF 逻辑对照兼容性矩阵检查内核配置，否则开机会弹"设备内部出现了问题"。

## 做了什么

- **BakaSU**（上游 main，内置，SUSFS inline hook 模式）；管理器用同一提交的 CI 构建。
- **SUSFS 2.3.0**：以 kafuuchino-s 对小米 MIX 4 的 5.4 回移为基础，在 ACK 5.4.276 上手工合并了 4 处，并按上游 BakaSU 当前的 hook 契约改了 2 处。
- **Droidspaces**：打开它要求的命名空间 / 消息队列 / devtmpfs / netfilter 选项，应用它的两个 kABI 补丁（新字段进 `ANDROID_KABI_RESERVE` 槽位，CRC 不变）；另开 `CFS_BANDWIDTH`（容器 CPU 限额 `--cpus`），用两行 `__GENKSYMS__` 遮挡把 CRC 保持不变。
- **修一个原厂 bug**：展讯 `CONFIG_XFRM_FRAGMENT` 的 sysctl 用单个全局指针、每个网络命名空间退出都释放一次，两个 netns 先后退出就二次释放、内核 panic（停带 systemd 的容器必现）。补丁 0007 只在 init_net 注册它。
- 构建身份（`KBUILD_BUILD_*`、`.scmversion`）与原厂对齐，`uname -a` 逐字相同。
- 三道门禁脚本：配置漂移、VINTF 内核要求、模块 ABI；一个只换 kernel 的 boot 打包器（头部、ramdisk、vbmeta 块逐字节不变，AVB footer 只改偏移，与 APatch 的做法一致）。

## 使用范围与限制

- **型号 / 固件**：只在 W203DS、固件 20251013（`5.4.276-android12-9-gb4a927d994a0`）上验证。同平台其它型号或固件要先用 `scripts/audit_abi.py` 重新确认 ABI 闭合，详见 [docs/BUILDING.md](docs/BUILDING.md)。
- **前提**：BL 已解锁；手里有自己设备的原厂 `boot_a`、`vendor_boot_a` 备份和 `/vendor/lib/modules`；会用 BROM（`spd_dump`）救砖。A/B 的另一个槽在这台机器上不可启动，boot_a 坏了不会自动回退。
- **刻意关闭**：`CONFIG_SYSVIPC`、`CONFIG_IP6_NF_NAT`（Android 13 兼容性矩阵要求为 n，开了会弹窗）；`CONFIG_CGROUP_PIDS`（`module_layout` 的 CRC 变，205 个原厂模块全部拒载，实测）。依赖 SysV IPC 的容器软件会受限，容器的 `--pids-limit` 用不了。
- **没有**：KPM（BakaSU 不含）、LKM 模式（5.4 非 GKI 只能内置）、任何对 Play Integrity 之类远端校验的承诺。
- 这是个人设备上的工程记录，不提供支持；刷写有砖机风险，后果自负。

## 下载现成的构建

[Releases](https://github.com/dammu/zte-w2xxds-mods-kernel/releases) 里是作者机器上刷过、验收过的构建，每个 release 附：

| 文件 | 用途 |
| --- | --- |
| `boot_a-*.img` | 可直接刷 `boot_a` 的 64 MiB 镜像：原厂 20251013 的 `boot_a` 只换了 kernel，ramdisk、vbmeta 块原样 |
| `Image-*` | 裸 kernel Image，用 `scripts/pack_boot.py` 配自己备份的原厂 `boot_a` 打包 |
| `config-*.txt` | 该构建的完整 `.config` |
| `BakaSU_*-arm64-v8a-release.apk` | 与内核 uapi 配套的 BakaSU 管理器（上游 CI 构建，签名证书 `d3469712…`） |
| `SHA256SUMS` | 校验和 |

**只适用于 W203DS、固件 20251013、BL 已解锁。** 其它型号或固件请不要直接刷，先按 [docs/BUILDING.md](docs/BUILDING.md) 重做 ABI 审计。刷写与验收步骤见 [docs/FLASHING.md](docs/FLASHING.md)：只写 `boot_a`，手边留着原厂 `boot_a` 和 BROM 工具，第一次开机后打开管理器装 ksud 再重启一次。

## 仓库内容

| 目录 | 内容 |
| --- | --- |
| `docs/` | [CONTEXT](docs/CONTEXT.md) 机制 · [BUILDING](docs/BUILDING.md) 构建 · [FLASHING](docs/FLASHING.md) 刷写验收 · [UPDATING](docs/UPDATING.md) 跟进上游 · [DESIGN](docs/DESIGN.md) 决策与阶段记录 |
| `patches/zte-5.4.276-bakasu-susfs-droidspaces/` | 现行补丁系列（7 个），打在 ZTE 开源树上 |
| `patches/alt-manual-hook/` | 不带 SUSFS 的替代方案：BakaSU 手动 hook |
| `configs/` | 原厂 `/proc/config.gz` 文本，以及三个配置片段（手动 hook / SUSFS / SUSFS + Droidspaces，现行为后者） |
| `scripts/` | VM 环境、构建、ABI 与 VINTF 审计、boot 打包、证书与内置固件提取、刷后验收 |
| `certs/` | 原厂模块签名证书（公钥，从原厂 kernel Image 提取） |
| `abi/` | 原厂 205 个模块引用的符号与 CRC 表（20251013 固件），审计输入 |

不在仓库里：原厂镜像和模块、构建产物、设备上的 VINTF 矩阵（构建前从设备 `/system/etc/vintf/` 拉取）。

## 快速路线

1. 按 [docs/BUILDING.md](docs/BUILDING.md) 搭环境（Ubuntu，36 GB 内存以上，clang r416183b），准备原厂材料和 ABI 表。
2. 先跑纯净基线 `scripts/vm-build-baseline.sh`，ABI 审计必须 0 不匹配。
3. `git am patches/zte-5.4.276-bakasu-susfs-droidspaces/*.patch`，跑 `scripts/vm-build-p4b.sh`。
4. `scripts/pack_boot.py <原厂 boot_a> out/arch/arm64/boot/Image boot_a-new.img`。
5. 按 [docs/FLASHING.md](docs/FLASHING.md) 刷 `boot_a` 并验收；第一次开机后打开管理器装 ksud，再重启一次。

## 参考与致谢

- [Ssrml/android_kernel_zte_ums9620_p720_w205ds](https://github.com/Ssrml/android_kernel_zte_ums9620_p720_w205ds)：ZTE 开源内核树的 GitHub 镜像（W205DS 的 drop，与 W203DS 固件同源）
- [WiteTanuki/W200DS-SukiSU-Kernel](https://github.com/WiteTanuki/W200DS-SukiSU-Kernel)：同平台的 SukiSU + SUSFS 2.2.0 移植；ABI 闭合方法、OEM 证书用法、可复现构建和 5.4 hook 位置都参照了它
- [Baka-SU/BakaSU](https://github.com/Baka-SU/BakaSU)（[文档](https://bakasu.org)）：root 方案本体
- [simonpunk/susfs4ksu](https://gitlab.com/simonpunk/susfs4ksu)：SUSFS 上游；[kafuuchino-s/susfs4ksu](https://github.com/kafuuchino-s/susfs4ksu) `mix4-5.4`：2.3.0 到 5.4 的回移；[kafuuchino-s/kernel_xiaomi_odin](https://github.com/kafuuchino-s/kernel_xiaomi_odin)：它的 ABI 审计思路
- [ravindu644/Droidspaces-OSS](https://github.com/ravindu644/Droidspaces-OSS)：容器运行时及其内核配置文档和 kABI 补丁
- [tiann/KernelSU](https://github.com/tiann/KernelSU)：元模块机制与模块规范；[backslashxx/mountify](https://github.com/backslashxx/mountify)：在用的元模块
- [TomKing062/spreadtrum_flash](https://github.com/TomKing062/spreadtrum_flash)：`spd_dump`，BROM 备份与救砖

## License

MIT for the contents of this repository. The kernel patches modify GPL-2.0 code and are GPL-2.0 when applied; BakaSU, SUSFS and Droidspaces keep their own licenses.
