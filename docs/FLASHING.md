# FLASHING — 刷写、验收、回退

每次只改一个变量，只写 `boot_a`。设备 A/B 的 `_b` 槽不可启动，**boot_a 起不来不会自动回退**，只能靠 BROM 人工救回，所以刷前的三道门禁一道都不能省。

## 1. 刷前

- [ ] 构建日志里 diffconfig 的漂移全部是预期的；VINTF 门禁通过；ABI 审计 `MISMATCH: 0 MISSING: 0`。
- [ ] `pack_boot.py` 校验通过，记下 boot 镜像 sha256。
- [ ] 手边有上一版能开机的 `boot_a` 镜像，以及 BROM 工具（`spd_dump` + FDL）。
- [ ] 管理器 APK 与内核同一版本（uapi 一致）；BakaSU 管理器不在 GitHub Releases，取 nightly.link 的 `Manager-release.zip`，签名证书必须是内核 `manager_sign.h` 里的那把（`apksigner verify --print-certs` 核对 sha256）。
- [ ] 设备空闲：没有正在用的远程会话；电量够；虚拟机软件没有占着设备的 USB。
- [ ] 如需无人值守验收：设备没有锁屏密码，`adb shell input keyevent KEYCODE_WAKEUP; wm dismiss-keyguard` 能解锁。

## 2. 刷写

```
adb reboot bootloader
fastboot getvar current-slot          # 必须是 a
fastboot getvar partition-size:boot_a # 0x4000000
fastboot flash boot_a boot_a-new.img
fastboot reboot
```

不 `fastboot boot`，不 `set_active`，不碰其它分区。Windows 上 UNISOC 的 `sprdadb.inf` 驱动能识别 fastboot 模式。

## 3. 开机后

- 重启后 USB 可能退回 MIDI-only；adb 不出现时在设备上把 USB 用途切回文件传输。
- 把 `scripts/postcheck.sh` push 到 `/data/local/tmp`，root 下执行。看：`uname -a`、模块数（203）、`getenforce`（Enforcing）、dmesg 里没有 `module verification failed`、触摸驱动（himax_tp）、Wi‑Fi、`/data/adb/metamodule`、模块挂载、su 上下文（`u:r:ksu:s0`）。
- 同时扫一遍：`dmesg -l err` 为空、`/data/tombstones` 没新文件、`logcat -b system` 里没有 HAL 重启、`avc: denied … permissive=0` 只有原厂也有的几条、没有弹"设备内部出现了问题"（窗口列表里没有 ErrorDialog）。
- **第一次刷 BakaSU 内核**：打开管理器 → 它装 ksud → 在"超级用户"里给 Shell 授权 → 再重启一次 → 模块（元模块、Zygisk、LSPosed 等）才会起来。此后换内核不需要这一步。
- SUSFS 配置用 `ksud susfs config …`（或管理器的 SUSFS 页面），`ksud susfs show version` 应显示 v2.3.0。
- Droidspaces：`droidspaces check` 必需项全过；起一个容器确认命名空间、网络（容器内要跑 DHCP 客户端）。

## 4. 回退

- fastboot 可用：`fastboot flash boot_a <上一版 boot_a.img>`。
- 起不来：BROM 模式（关机，电源 + 音量减），`spd_dump exec_addr … fdl … write_part boot_a <镜像> reset`。只写 `boot_a`，不要整体恢复全分区。
- 换回 APatch 等其它 root 方案时，`/data/adb` 下各自的目录互不删除，写回对应的 boot 即恢复。

## 5. 管理器与版本错位的症状

| 现象 | 含义 |
| --- | --- |
| 管理器"需要更新管理器" | 管理器版本码/uapi 低于内核 |
| 管理器"需要更新内核" | 管理器 uapi 高于内核；ksud 可能用到内核没有的 ioctl |
| 管理器"工作中"但没有模块挂载 | ksud 还没装或本次开机前不存在，重启 |
| 开机弹"设备内部出现了问题" | VINTF 内核要求不满足，用 `audit_vintf_kernel.py` 找是哪个 CONFIG |
