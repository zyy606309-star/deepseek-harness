#!/bin/bash
# xiaojianbang-syscall-filter KPM 加载/控制脚本（在 PC 上通过 adb 操作设备）
#
# 作者：小肩膀   微信：xiaojianbang8888
#
# 用法:
#   ./load.sh load            加载模块
#   ./load.sh unload          卸载模块
#   ./load.sh status          查看运行状态
#   ./load.sh list            列出已加载模块
#   ./load.sh ctl 'AOSP=off'  运行时控制（参数必须无空格）
#   ./load.sh reload          重新推送并加载（改完代码后用）
#   ./load.sh push-kpatch     推送内置 kpatch 到设备 /data/local/tmp/kpatch
#
# 控制命令(单 token，无空格):
#   trace=on|off  fake=on|off  dump=on|off  exitmon=on|off
#   memmon=on|off  memdump=on|off  resolve=on|off
#   sysmon=on|off
#   ROOT=on|off  FRIDA=on|off  XPOSED=on|off  AOSP=on|off
#   uidadd=10299  uiddel=10299  uidclear  status
#
# 环境变量:
#   XJB_ADB=/path/to/adb             覆盖 adb；未设置时用 ADB，再回退 PATH 中的 adb
#   XJB_KP_SUPERKEY=your_superkey    覆盖 KernelPatch/APatch superkey
#   XJB_KPATCH_LOCAL=/path/kpatch    覆盖本地 kpatch 二进制

set -e
ADB="${XJB_ADB:-${ADB:-adb}}"
ADB_TIMEOUT="${ADB_TIMEOUT:-30s}"
KP="/data/local/tmp/kpatch"
SK="${XJB_KP_SUPERKEY:-xiaojianbang8888}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
KPM_LOCAL="$SCRIPT_DIR/syscallhook.kpm"
KP_LOCAL="${XJB_KPATCH_LOCAL:-$SCRIPT_DIR/../kernelpatch-kpatch/kpatch}"
KPM_DEV=/data/local/tmp/scfilter.kpm
NAME=xiaojianbang-syscall-filter

run_with_timeout() {
  if command -v timeout >/dev/null 2>&1; then
    timeout "$ADB_TIMEOUT" "$@"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$ADB_TIMEOUT" "$@"
  else
    "$@"
  fi
}
adb_cmd() { run_with_timeout "$ADB" "$@"; }
dev() { adb_cmd shell su -c "$*"; }

push_kpatch() {
  if [ ! -f "$KP_LOCAL" ]; then
    echo "找不到本地 kpatch: $KP_LOCAL" >&2
    echo "可用 XJB_KPATCH_LOCAL=/path/to/kpatch 覆盖。" >&2
    exit 1
  fi
  adb_cmd push "$KP_LOCAL" "$KP"
  dev "chmod 755 $KP"
  echo "kpatch pushed: $KP"
}

ensure_kpatch() {
  adb_cmd shell "test -x $KP" >/dev/null 2>&1 || push_kpatch
}

case "$1" in
  push-kpatch|kpatch)
    push_kpatch
    ;;
  load)
    ensure_kpatch
    dev "$KP $SK kpm load $KPM_DEV"
    ;;
  unload)
    ensure_kpatch
    dev "$KP $SK kpm unload $NAME"
    ;;
  status)
    ensure_kpatch
    dev "$KP $SK kpm ctl0 $NAME status >/dev/null"
    dev "dmesg | grep -E '\[scfilter\] status(_cat|_uid|_compat)?:' | tail -5"
    echo
    ;;
  list)
    ensure_kpatch
    dev "$KP $SK kpm list"
    echo
    ;;
  info)
    ensure_kpatch
    dev "$KP $SK kpm info $NAME"
    ;;
  ctl)
    if [ -z "${2:-}" ]; then
      echo "ctl 需要一个无空格控制命令，例如: $0 ctl 'resolve=on'" >&2
      exit 1
    fi
    ensure_kpatch
    dev "$KP $SK kpm ctl0 $NAME '$2' >/dev/null"
    dev "dmesg | grep -E '\[scfilter\] status(_cat|_uid|_compat)?:' | tail -5"
    echo
    ;;
  push)
    adb_cmd push "$KPM_LOCAL" "$KPM_DEV"
    echo "pushed"
    ;;
  reload)
    ensure_kpatch
    adb_cmd push "$KPM_LOCAL" "$KPM_DEV"
    dev "$KP $SK kpm unload $NAME 2>/dev/null; $KP $SK kpm load $KPM_DEV"
    ;;
  *)
    echo "用法: $0 {load|unload|status|list|info|push|push-kpatch|reload|ctl '<cmd>'}"
    exit 1
    ;;
esac
