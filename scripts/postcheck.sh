#!/system/bin/sh
# Post-flash verification, read-only. Run as root: su -c 'sh /data/local/tmp/postcheck.sh'
echo "== uname"; uname -a
echo "== uuremote: $(ps -A | grep -c uuremote)"
echo "== slot=$(getprop ro.boot.slot_suffix) bootstate=$(getprop ro.boot.verifiedbootstate) selinux=$(getenforce)"
echo "== boot_completed=$(getprop sys.boot_completed) uptime=$(cut -d' ' -f1 /proc/uptime)s"
echo "== modules loaded: $(wc -l < /proc/modules) (expect 203)"
echo "== module verification / taint / ksu in dmesg:"
dmesg | grep -iE "module verification|tainted|signature|KernelSU|ksu|kernelsu" | grep -viE "susfs" | head -25
echo "== missing modules vs modules.load:"
for m in $(cat /vendor/lib/modules/modules.load); do n=$(basename $m .ko | tr - _); grep -q "^$n " /proc/modules || echo "  NOT LOADED: $m"; done
echo "== touch/himax: $(ls /sys/bus/spi/devices/spi1.0/driver 2>/dev/null && readlink /sys/bus/spi/devices/spi1.0/driver)"
echo "== input devices: $(cat /proc/bus/input/devices | grep -c '^N:')"
echo "== wifi: $(getprop wlan.driver.status) iface=$(ip -o link | grep -c wlan)"
echo "== ksud: $(ls -la /data/adb/ksud 2>&1)"
echo "== metamodule: $(readlink /data/adb/metamodule 2>&1)"
echo "== /data/adb entries: $(ls /data/adb | tr '\n' ' ')"
echo "== mounts by modules (system/bin overlays):"; grep -E "adb|mountify|KSU|ksu" /proc/mounts | head -10
echo "== su: $(which su) ctx=$(id)"
echo "== manager app: $(pm list packages | grep -iE 'bakasu|resukisu|kernelsu|weishu' )"
echo "== lsposed/zygisk procs: $(ps -A | grep -cE 'zygiskd|lspd')"
echo "== default_home=$(settings get secure default_home) remoteswitch_mode=$(settings get secure remoteswitch_mode)"
echo "== last kernel panic/pstore:"; ls /sys/fs/pstore 2>/dev/null | head
