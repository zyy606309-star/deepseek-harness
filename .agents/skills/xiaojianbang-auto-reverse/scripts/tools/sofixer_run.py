# -*- coding: utf-8 -*-
"""sofixer 一键修复脚本 —— 封装 python-sofixer，简化调用。

用法示例:
    python sofixer_run.py -s dumped.so -o fixed.so -m 0x7c17af5000
    python sofixer_run.py -s dumped.so -o fixed.so -m 0x7c17af5000 -b original.so
    python sofixer_run.py -s dumped.so -o fixed.so -m 0x7c17af5000 -d
    或 (交互式)  python sofixer_run.py

说明:
    -s  待修复的 dump 出来 so (必须)
    -o  修复后输出的 so 路径 (必须)
    -m  dump 时的内存基地址 (必须, 十六进制如 0xABC 或十进制)
    -b  可选的原始 so 路径 (用于动态段恢复, 实验性)
    -d  打印 debug 日志
"""
import argparse
import os
import sys
import traceback

# 让 python-sofixer 可被导入
ROOT = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(ROOT, "python-sofixer")
sys.path.insert(0, TOOLS)

try:
    from src.sofixer.main import fix_so_file
except Exception as e:
    print(f"[!] 导入 sofixer 失败: {e}")
    print("    请确认目录下存在 python-sofixer/ 子目录。")
    sys.exit(1)


def main():
    p = argparse.ArgumentParser(description="SoFixer - 修复 dump 出来的 so 文件")
    p.add_argument("-s", "--source", required=True, help="待修复的 dump so")
    p.add_argument("-o", "--output", required=True, help="修复后输出 so")
    p.add_argument("-m", "--memso", required=True, help="dump 时的内存基地址(hex)")
    p.add_argument("-b", "--baseso", default=None, help="原始 so 路径(可选)")
    p.add_argument("-d", "--debug", action="store_true", help="打印 debug 日志")
    args = p.parse_args()

    if not os.path.isfile(args.source):
        print(f"[!] 源文件不存在: {args.source}")
        sys.exit(1)

    base = args.memso
    # 若是纯十六进制（不带 0x），自动补 0x
    if not base.lower().startswith("0x"):
        base = "0x" + base

    print(f"== SoFixer 开始修复 ==")
    print(f"   输入: {args.source}")
    print(f"   输出: {args.output}")
    print(f"   基址: {base}")
    try:
        ok = fix_so_file(
            dumped_path=args.source,
            output_path=args.output,
            dump_base_addr=base,
            base_so_path=args.baseso,
            debug=args.debug,
        )
        if ok:
            size = os.path.getsize(args.output)
            print(f"== 修复成功! 输出 {size} 字节 → {args.output}")
            sys.exit(0)
        else:
            print("== 修复失败 (详情见上方日志) ==")
            sys.exit(1)
    except Exception as e:
        print(f"[!] 异常: {e}")
        if args.debug:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
