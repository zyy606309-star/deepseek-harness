# SoFixer（Python 版）+ sofixer_run.py

用于修复从内存 dump 出来的**畸形 ELF**（`--raw` / syscall dump / 手工地址 dump 等未自动修复的产物），使其能被 rizin / IDA / Binary Ninja 正常解析。

## 上游出处

- 原版 C++ 实现：**F8LEFT/SoFixer** — https://github.com/F8LEFT/SoFixer
- 本目录 `python-sofixer/` 是纯 Python 移植版（借助 AI 从 F8LEFT 原版移植），功能等价：修程序头、重建段头表、处理动态段/重定位。
- 本目录保留了移植版自带的 `README.md` / `USAGE.md` / `setup.py` / `requirements.txt`，以及源码 `src/`、诊断工具 `tools/`、测试 `tests/`。已剔除移植副本里的 `.git`、`__pycache__`、`.vscode`、`debug/` 调试产物等非工具本体内容。

> 许可证：原版 SoFixer 与移植版均未随本目录携带 LICENSE 文件；如对外再分发，请自行核对上游许可证。

## 用法

`sofixer_run.py` 是 python-sofixer 的一键封装，放在本目录（`scripts/tools/`）下，它会在**同目录**的 `python-sofixer/` 里查找源码并导入。

```bash
# 一键修复（-m 必须 = dump 时的内存基地址，十六进制）
python scripts/tools/sofixer_run.py -s dump.so -o fixed.so -m 0x7c17af5000

# 可选：-b 原始 so（辅助恢复动态段，实验性）；-d 打印 debug
python scripts/tools/sofixer_run.py -s dump.so -o fixed.so -m 0x7c17af5000 -b original.so -d
```

要点：

- **`-m` 必须与 dump 时记录的内存基址一致**，否则段地址对不上、修出来仍乱。由 dump 记录/base 决定，不能猜。
- 自动识别 ELF 是 32/64 位，无需手动指定。
- 修复后必须校验：`rz-bin -I fixed.so` 或 `file fixed.so`，确认 `ELF64/ELF32, class, arch` 正常后再进 rizin/IDA。校验不过则说明镜像或 `-m` 有误。
- 模块 API：`from src.sofixer.main import fix_so_file; fix_so_file('dump.so','fixed.so',0x7c17af5000)`（在 `python-sofixer/` 目录下运行）；不要用 `python -m src.sofixer.main`（有模块重复导入的坑）。

依赖：纯 Python 标准库（ctypes / mmap / struct / logging / argparse / os / sys / tempfile / typing），无第三方包。
