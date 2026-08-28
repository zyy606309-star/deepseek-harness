# rizin / Ghidra 工具链（本模式默认）

> 本文是「工具层」说明：默认用 **rizin 反汇编 + Ghidra headless 伪代码回退** 替代 IDA/`INP.py`，用于 `.so` 静态分析、函数范围确认和 AI 输入导出。方法论本体（检测链、硬门禁、静态顺序、函数范围、CRC、patch 边界、记录）**不在此改**，仍见 `workflow-standards.md`。需要 IDA 时按 `tooling-and-paths.md` 的 IDA 条款走（仅用户明确要求）。

## 定位

- **rizin**：反汇编（权威视图）、字符串、导入/导出、符号、段、xref、函数列表。rizin 0.8.2 未装 ghidra 插件（`pdc`/`pdg` 不存在），**不能出伪代码**。
- **Ghidra headless（`analyzeHeadless`）**：伪代码（等价 Hex-Rays 的辅助视图），可选；按本机配置启用。
- 二者配合：rizin 出反汇编（证据权威），Ghidra 出伪代码（辅助理解），**伪代码必须对照反汇编交叉验证**，不单独作为 patch 依据。

## 工具入口

| 需要 | 命令 | 产物 |
|---|---|---|
| 导出 AI 输入 + 反汇编 + 伪代码 | `python3 scripts/tools/rizin_export.py <so> <out_dir> --ghidra-support <ghidra>/support` | `artifacts/inp/<模块>_export_for_ai/` |
| 只要反汇编/元数据（无伪代码） | `python3 scripts/tools/rizin_export.py <so> <out_dir>` 或加 `--no-ghidra` | 同上（无 `ghidra_pseudocode/`） |
| 单个函数反汇编 | `rizin -q -c 's <addr>; af; pdf' <so>` | stdout |
| 函数列表 | `rizin -A -q -c aflj <so>` | JSON |
| 字符串 | `rz-bin -zj <so>` | JSON |
| 导入/导出/符号/段 | `rz-bin -ij/-Ej/-sj/-Sj <so>` | JSON |
| xref | `rizin -q -c 's <addr>; axt' <so>` | stdout |

`rizin`/`rz-bin` 需在 PATH（本机：`C:\Program Files\Rizin\bin`）。

## rizin_export.py 产物

输出到 `<out_dir>/`（按惯例是 `artifacts/inp/<模块>_export_for_ai/`）：

```
meta.json            工具版本、目标
rzbin_info.txt       header 摘要
info/sections/segments/symbols/imports/entry.json   二进制元数据
strings.json         候选字符串（string/offset/size/section）
functions.json       rizin 函数列表
functions_map.json   地址→函数名映射（用于 offset 定位）
disassembly.txt      权威：每个函数反汇编 + xref
EXPORT_README.md     说明
pseudocode_note.txt  Ghidra 状态
ghidra_pseudocode/   （可选）各函数 .c + index.txt
```

## 关键注意

- **Windows 路径**：`rizin_export.py` 传给 Ghidra `.bat` 的路径已自动转正斜杠（cmd 不吃反斜杠），无需手动处理。
- **伪代码是可选回退**：Ghidra 未配置时脚本自动跳过，只出反汇编；不阻塞主链。Ghidra 12.0.3 需 JDK 21+（本机用 `D:\openjdk-21.0.2_windows-x64_bin`），启动较慢（首次约 100s+），仅在需要伪代码时启用。
- **函数范围确认**：用 `functions.json` 核对起止地址，范围异常时按 `workflow-standards.md` §6 处理（rizin 无现成范围修正脚本，参考 `functions_map.json` 人工确认后重新导出）。
- **OLLVM 还原**：仍用 `OLLVM_Deobfuscator`（纯 Python，与 rizin 无关）；还原结果用 rizin 重新导出关键函数文本交叉验证。
- 环境事实（本机 rizin/jadx 路径、f14、设备）见 `environment.md`。

## 与 IDA 的取舍

- 默认 rizin/rizin+Ghidra。用户明确要求或用 IDA 导出时，才切 IDA + `INP.py`（见 `tool-installation.md`）。
- 结论的**证据基础 = 反汇编**（比伪代码可靠），伪代码只用于快速理解，最终 patch 依据回到反汇编 + 动态证据。
