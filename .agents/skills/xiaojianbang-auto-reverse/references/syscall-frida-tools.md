# syscall-filter、Frida 联合采集与证据提取

## 目录

- xiaojianbang-syscall-filter
- Frida + syscall-filter runner
- 关键证据提取

## xiaojianbang-syscall-filter

用途：

- syscall 层定位 `kill/tgkill/exit/exit_group`。
- 捕获 `SIGSEGV/SIGTRAP/SIGABRT/BRK` 相关证据。
- 捕获 root/frida/xposed/模拟器路径访问，如 `faccessat/openat/readlinkat/statx`。
- 支持 arm64 App 和 arm32 compat App；arm32 日志会带 `abi:arm32`，`mmap2` 会输出 `off_bytes`。
- 通过 `resolve=on` 在进程死亡前解析 `pc/lr -> so!offset` 或 `anon:base+offset`。

常用命令：

```bash
cd third_party/xiaojianbang-syscall-filter
./load.sh reload
./load.sh ctl 'uidadd=<目标UID>'
./load.sh ctl 'resolve=on'
./load.sh ctl 'exitmon=on'
./capture_test.sh com.example.target <目标UID> target 12
cat logs/target_resolved.log
```

注意：

- `load.sh` / `load.ps1` 默认使用设备端 `/data/local/tmp/kpatch`。如果设备缺少该文件，会从项目副本 `third_party/kernelpatch-kpatch/kpatch` 自动推送；也可手动运行 `./load.sh push-kpatch`。
- superkey 默认值为 `xiaojianbang8888`，可用 `XJB_KP_SUPERKEY` 覆盖；本地 kpatch 路径可用 `XJB_KPATCH_LOCAL` 覆盖。
- 若 `adb` 不在 `PATH` 中，使用 `XJB_ADB=/path/to/adb` 覆盖。
- `exitmon` 只记录退出/信号 syscall，不应默认伪造退出结果。
- Skill 分发版不包含 scfilter KPM 源码；需要改规则或重新适配内核时，用源码版构建新的 `syscallhook.kpm` 后替换。

## Frida + syscall-filter runner

`scripts/tools/frida_scfilter_runner.py` 是通用 runner。它会同时：

- Frida spawn 目标包。
- 加载 pre-script 和主 Frida agent。
- 可选 spawn-gating 覆盖子进程。
- 采集 logcat。
- 采集 `[scfilter]` dmesg。
- 生成 raw/hits/resolved 三份 syscall-filter 日志。

示例：

```bash
python3 scripts/frida_scfilter_runner.py \
  --package com.example.target \
  --script ./scripts/agent_main.js \
  --pre-script ./bypass_frida_detection.js \
  --duration 180 \
  --spawn-target-regex '^com\.example\.target(:.*)?$' \
  --child-script ./scripts/agent_child.js \
  --tag stable_verify_$(date +%Y%m%d_%H%M%S)
```

路径选择：

- `XJB_SCF_ROOT` 可覆盖 syscall-filter 根目录。
- `XJB_ADB` 可覆盖 adb 路径。
- Windows/Linux/macOS 都支持；Windows 可用 `XJB_ADB=C:\path\adb.exe` 或工程内 `third_party\platform-tools\adb.exe`。
- 默认优先使用当前工程 `third_party/xiaojianbang-syscall-filter`。
- 如果工程没有本地副本，则使用 Skill 内置 `scripts/tools/xiaojianbang-syscall-filter`。
- `--uid` 可省略，runner 会通过 `cmd package list packages -U` 或 `dumpsys package` 自动解析；解析失败时再手动传 `--uid`。

## 关键证据提取

`scripts/collect_key_evidence.py` 从日志、文本和实验记录中提取闪退、加载链、root/frida/hook、patch、ANR 等决定性行。

示例：

```bash
python3 scripts/collect_key_evidence.py logs/ docs/experiment_record.md \
  --so libtarget.so \
  --pattern 'uid:10239|pc=.*libtarget' \
  --context 2 \
  --out logs/key_evidence.md
```

要点：

- 内置正则只覆盖常见 syscall、加载链、patch 和历史案例 so；新目标必须用 `--so` 或 `--pattern` 补充目标特征。
- 输出只作为证据索引，结论仍需回到原始日志、IDA 导出和实验记录交叉确认。
