# dexfixer 与抽取式脱壳合并工具

## 使用前提

`dexfix_runner.py` 只用于小肩膀定制系统抽取式加固脱壳产物。使用前必须先按 `references/custom-system.md` 询问并记录设备是否为「小肩膀定制系统」。

## dexfixer / dexfix_runner

用途：

- 小肩膀定制系统抽取式加固脱壳会生成 `.dex`（不完整 dex）+ `.bin`（方法体数据）+ `.txt`（类名）。
- `dexfixer.jar` 把同名 `.dex` 与 `.bin` 合并为完整 dex。
- `dexfix_runner.py` 封装批量拉取 + 配对合并。

Skill 内置：

```text
scripts/tools/dexfixer/dexfixer.jar
scripts/tools/dexfix_runner.py
```

批量模式（默认，需 adb + 设备 root）：

```bash
python3 scripts/dexfix_runner.py \
  --package com.example.target \
  --out-dir artifacts/dexfix
```

本地合并（已手动拉回 .dex/.bin，不走 adb）：

```bash
python3 scripts/dexfix_runner.py \
  --src-dir artifacts/dexfix/pulled \
  --out-dir artifacts/dexfix \
  --no-pull
```

单对透传：

```bash
python3 scripts/dexfix_runner.py \
  --dex classes.dex --bin classes.bin --out classes.fixed.dex
```

注意：

- 设备脱壳目录默认 `/data/data/<package>/xiaojianbang`（抽取式脱壳实际产物目录，不是 `/data/local/tmp/<package>` 启用目录）；其他目录用 `--device-dir`。
- wrapper 经 `/sdcard` 中转再 pull，因为 app 私有目录不能直接 `adb pull`。
- 宿主机需要 `java`；`XJB_JAVA` 可覆盖，`XJB_DEXFIXER_JAR` 可覆盖 jar 路径，`XJB_ADB` 可覆盖 adb。
- 只有 `.dex` 无同名 `.bin` 的会跳过（多为整体脱壳的完整 dex，无需合并）。
- 合并后用 garlic（首选）或 jadx 复核 dex 完整性和方法体还原情况；jadx 必须关闭 checksum 校验。
