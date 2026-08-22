# Skill 内置工具索引

本文件只做工具导航。需要具体命令时按任务读取对应 reference，避免为单个工具加载完整长文档。

## 目录

- 工具目录
- 读取路由
- 工具分流速查

## 工具目录

```text
scripts/tools/
├── frida_scfilter_runner.py
├── frida_memdump_so.py
├── INP.py
├── ida_fix_function_range.py
├── memdump_so.py
├── ecapture_android.py
├── stealth_hook_android.py
├── dexfix_runner.py
├── kernelpatch-kpatch/
│   └── kpatch
├── dexfixer/
│   └── dexfixer.jar
├── ecapture-v2.3.0-android-arm64/
├── MemDumper/
├── ollvm_deobfuscator/
├── xiaojianbang-stealth-hook/
└── xiaojianbang-syscall-filter/
```

Skill 内不应包含历史采集日志、`.git`、`__pycache__`、`.pyc`、native 源码、编译中间文件、测试 APK 和非必需样本 so。发现缓存、源码或临时产物时先清理，再分发或复制工具。

## 读取路由

- 工具复制、`--audit`、`--self-check`、`--with-runner`、`INP.py` 安装语义：读 `references/tool-installation.md`。
- `xiaojianbang-syscall-filter`、Frida 联合采集、关键证据提取：读 `references/syscall-frida-tools.md`。
- MemDumper 分流、短窗口 dump/fix、IDA 导出、函数范围修正、OLLVM 还原：读 `references/dump-ida-ollvm-tools.md`。
- 内核无痕 HWBP hook、eCapture Android arm64：读 `references/stealth-ecapture-tools.md`。
- 小肩膀定制系统抽取式脱壳合并、`dexfix_runner.py`：读 `references/dexfix-tools.md`，并先按 `references/custom-system.md` 确认定制系统。

## 工具分流速查

| 目标 | 首选工具 | 详情 |
| --- | --- | --- |
| 复制内置工具到工程 | `scripts/install_skill_tools.py` | `tool-installation.md` |
| 全新设备补齐 KernelPatch CLI | `kernelpatch-kpatch/kpatch` / `load.sh push-kpatch` | `tool-installation.md` |
| syscall/direct syscall/闪退 pc/lr | `xiaojianbang-syscall-filter` / `frida_scfilter_runner.py` | `syscall-frida-tools.md` |
| 稳定进程已加载 so dump/fix | `memdump_so.py` | `dump-ida-ollvm-tools.md` |
| constructor 短窗口或快速闪退 dump/fix | `frida_memdump_so.py` | `dump-ida-ollvm-tools.md` |
| IDA 导出 AI 输入 | `INP.py` | `dump-ida-ollvm-tools.md` |
| IDA 函数范围修正 | `ida_fix_function_range.py` | `dump-ida-ollvm-tools.md` |
| OLLVM/CFF/间接跳转还原 | `OLLVM_Deobfuscator` | `dump-ida-ollvm-tools.md` |
| 强反 Frida / 强 CRC 场景无痕验证 | `stealth_hook_android.py` | `stealth-ecapture-tools.md` |
| TLS 明文/pcap/keylog | `ecapture_android.py` | `stealth-ecapture-tools.md` |
| 抽取式脱壳 `.dex` + `.bin` 合并 | `dexfix_runner.py` | `dexfix-tools.md` |
