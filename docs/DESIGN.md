# DESIGN — 决策与阶段记录

## 目标

把 W203DS 上的 APatch 换成自编内核 + BakaSU（内置）+ SUSFS，并补齐 Droidspaces 所需的内核选项，同时保持原厂模块全部可用、尽量与原厂不可区分、可重复构建与升级。

## 关键决策

| 决策 | 选择 | 原因 |
| --- | --- | --- |
| 源码基线 | ZTE 开源树（Ssrml 镜像）+ 本机 `/proc/config.gz` | 唯一能让 205 个原厂模块 CRC 全闭合的组合；W200DS 工程的树与它同源但缺 `drivers/vendor` |
| 只换 kernel Image | 原厂 `boot_a` 容器，ramdisk/vbmeta 不动 | APatch 已证明解锁态下可行；最小改动面 |
| 模块签名 | 保留 `MODULE_SIG_FORCE`，把原厂证书放进 `SYSTEM_TRUSTED_KEYS` | 不留下"签名强制被关"的痕迹 |
| Root | BakaSU 上游 main，内置 | 第三方 5.4 分支（kafuuchino）没有能用的签名管理器；上游在 5.4 上直接可编 |
| Hook 模式 | SUSFS inline hook（最终）；手动 hook 作为无 SUSFS 的备选 | 5.4 非 GKI 不能用 tracepoint |
| SUSFS | 2.3.0，用 kafuuchino 的 5.4 回移为基础 | 唯一现成的 5.4 + BakaSU 组合；W200DS 的 2.2.0 用作 hook 位置参照 |
| Droidspaces | 开必需 + 推荐选项，打两个 kABI 补丁；`CFS_BANDWIDTH`/`CGROUP_PIDS` 不开 | kABI |
| VINTF | 关掉矩阵要求为 n 的 `SYSVIPC`、`IP6_NF_NAT`，不改矩阵 | 改矩阵是改体检表而不是改不合格项，且要动 `/system` |
| 元模块 | 沿用 Mountify | 已验证，挂载被 SUSFS 自动隐藏，有 tmpfs 后端 |
| SUSFS 配置 | ksud 自带的持久化配置，不用 susfs4ksu-module | 该模块只到 SUSFS 2.1，而 ksud 自带开机下发 |
| 构建身份 | `KBUILD_BUILD_*` 与 `.scmversion` 对齐原厂 | `uname -a` 逐字相同 |

## 阶段记录

| 阶段 | 内容 | 结果 |
| --- | --- | --- |
| P1 | 纯净基线：ZTE 树 + 原厂 config | Image 尺寸与原厂相同；2209 符号 0 不匹配。需补 5 个内置触摸固件和空 `fw_sample.i`；VM 24 GB 内存链接 OOM，36 GB 通过 |
| P2 | BakaSU（kafuuchino mix4-5.4）手动 hook | 刷入一次开机；但管理器 uapi 错位（内核 35231/5，可用管理器只有 35171/4 和 35252/6） |
| P2b | 改用上游 BakaSU main（35252/6） | 上游直接可编，fstat hook 契约改为 `ksu_handle_newfstat_ret`；刷入后 ksud/元模块/LSPosed/Zygisk 全部恢复 |
| P3 | SUSFS 2.3.0 inline hook | 28 文件中 4 hunk 手工合并，2 处上游契约适配；`uname` 对齐原厂；无人值守刷入一次成功 |
| P4 | Droidspaces 选项 + kABI 补丁 | ABI 仍闭合；`droidspaces check` 全过；但 `SYSVIPC`/`IP6_NF_NAT` 触发 VINTF 弹窗 |
| P4b | 去掉这两项 | 弹窗消失；`check` 必需项仍全过；**现行版本** |

## 验证过的与没验证的

验证过：原厂模块全部加载；触摸、Wi‑Fi、蓝牙、USB；SELinux enforcing；元模块挂载、Zygisk Next、Sui、LSPosed；SUSFS 隐藏对非 su 进程生效；Droidspaces NAT 容器（CLI 与守护进程两种路径）在 SUSFS 隐藏开启时正常；开机无内核错误、无 tombstone、无 HAL 重启。

没验证：长期运行（休眠唤醒、热、相机、通话）；Droidspaces `--privileged`、`-P`、systemd 镜像；依赖 SysV IPC 的容器软件；Play Integrity 之类远端校验。

## 已知差异（相对原厂，可被观察到的）

- `/proc/config.gz` 含 `CONFIG_KSU*`（普通应用读不到，shell/system 域能读）。
- sepolicy 多出 `droidspacesd` permissive 域（来自 Droidspaces 模块，可关守护进程模式）。
- 元模块的挂载（已由 SUSFS 对非 su 进程隐藏）。
