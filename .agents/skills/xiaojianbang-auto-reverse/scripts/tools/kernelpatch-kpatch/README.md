# KernelPatch kpatch

Android arm64 `kpatch` CLI for APatch/KernelPatch KPM loading and `ctl0` control.

Default device path used by `xiaojianbang-syscall-filter/load.sh`:

```text
/data/local/tmp/kpatch
```

The bundled `xiaojianbang-syscall-filter/load.sh` and `load.ps1` can push this binary automatically when the device path is missing. Manual push:

```bash
adb push kpatch /data/local/tmp/kpatch
adb shell su -c 'chmod 755 /data/local/tmp/kpatch'
adb shell su -c '/data/local/tmp/kpatch xiaojianbang8888 hello'
```

Build provenance for this bundled binary:

```text
source: /home/xiaojianbang/bin/KernelPatch-main/user_deprecated
compiler: Android NDK aarch64-linux-android28-clang
features: hello, kpver/kver, kpm load/unload/list/info/ctl0
```
