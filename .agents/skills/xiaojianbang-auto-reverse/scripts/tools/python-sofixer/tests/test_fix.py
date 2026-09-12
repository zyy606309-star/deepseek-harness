#!/usr/bin/env python3
"""
测试修复后的Python版本ELF重建功能
=====================================

这个脚本用于验证修复后的Python版本能否正确生成与C++版本相同的ELF段结构。
"""

import sys
import os
import logging

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sofixer.elf_reader import ObfuscatedELFReader
from sofixer.elf_rebuilder import ELFRebuilder

# 配置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

def test_section_creation(input_file, dump_base_addr, output_file=None):
    """测试段头表创建"""
    print(f"测试文件: {input_file}")
    print(f"内存基地址: 0x{dump_base_addr:x}")
    print("=" * 80)

    try:
        # 初始化ELF读取器
        with ObfuscatedELFReader(input_file) as elf_reader:
            # 设置dump基地址
            elf_reader.set_dump_base_addr(dump_base_addr)

            # 加载ELF文件
            if not elf_reader.load():
                print("❌ ELF文件加载失败")
                return False

            print(f"✓ ELF文件加载成功")
            print(f"  架构: {'64位' if elf_reader.is_64bit else '32位'}")
            print(f"  程序头数量: {len(elf_reader.program_headers)}")
            print(f"  加载数据大小: 0x{len(elf_reader.loaded_data):x} 字节")

            # 计算加载大小
            min_vaddr, max_vaddr, load_size = elf_reader.calculate_load_size()
            print(f"  虚拟地址范围: 0x{min_vaddr:x} - 0x{max_vaddr:x}")
            print(f"  加载大小: 0x{load_size:x} 字节")

            # 初始化重建器
            rebuilder = ELFRebuilder(elf_reader)

            # 提取soinfo信息
            if not rebuilder.extract_so_info():
                print("❌ soinfo提取失败")
                return False

            print(f"✓ soinfo提取成功")

            # 检查关键字段
            so_info = rebuilder.so_info
            print(f"  动态段数量: {so_info.dynamic_count}")
            print(f"  符号表偏移: 0x{so_info.symtab_offset:x}")
            print(f"  字符串表大小: {so_info.strtabsize}")
            print(f"  哈希表条目: bucket={so_info.nbucket}, chain={so_info.nchain}")

            if hasattr(so_info, 'pad_size'):
                print(f"  填充大小: {so_info.pad_size} 字节")
            if hasattr(so_info, 'max_load'):
                print(f"  最大加载地址: 0x{so_info.max_load:x}")
            if hasattr(so_info, 'min_load'):
                print(f"  最小加载地址: 0x{so_info.min_load:x}")

            # 重建段头表
            if not rebuilder._rebuild_section_headers():
                print("❌ 段头表重建失败")
                return False

            print(f"✓ 段头表重建成功")
            print(f"  段数量: {len(rebuilder.section_headers)}")

            # 显示段信息
            print("\n段头表详情:")
            print(f"{'索引':<4} {'段名':<20} {'类型':<12} {'地址':<12} {'大小':<12}")
            print("-" * 72)

            for i, shdr in enumerate(rebuilder.section_headers):
                # 从字符串表获取段名
                if shdr['sh_name'] < len(rebuilder.shstrtab):
                    name_start = shdr['sh_name']
                    name_end = rebuilder.shstrtab.find(0, name_start)
                    if name_end == -1:
                        name_end = len(rebuilder.shstrtab)
                    name = rebuilder.shstrtab[name_start:name_end].decode('utf-8', errors='ignore')
                else:
                    name = f"<invalid:{shdr['sh_name']}>"

                # 段类型名称
                type_names = {
                    0: "NULL", 1: "PROGBITS", 2: "SYMTAB", 3: "STRTAB", 4: "RELA",
                    5: "HASH", 6: "DYNAMIC", 7: "NOTE", 8: "NOBITS", 9: "REL",
                    11: "DYNSYM", 14: "INIT_ARRAY", 15: "FINI_ARRAY", 0x70000001: "ARM_EXIDX"
                }
                type_name = type_names.get(shdr['sh_type'], f"{shdr['sh_type']}")

                print(f"{i:<4} {name:<20} {type_name:<12} 0x{shdr['sh_addr']:<10x} 0x{shdr['sh_size']:<10x}")

            # 检查关键段是否存在
            expected_sections = ['.dynsym', '.dynstr', '.hash', '.plt', '.text&ARM.extab', '.data', '.shstrtab']
            found_sections = []

            for shdr in rebuilder.section_headers:
                if shdr['sh_name'] < len(rebuilder.shstrtab):
                    name_start = shdr['sh_name']
                    name_end = rebuilder.shstrtab.find(0, name_start)
                    if name_end == -1:
                        name_end = len(rebuilder.shstrtab)
                    name = rebuilder.shstrtab[name_start:name_end].decode('utf-8', errors='ignore')
                    found_sections.append(name)

            print(f"\n关键段检查:")
            for expected in expected_sections:
                if expected in found_sections:
                    print(f"  ✓ {expected}")
                else:
                    print(f"  ❌ {expected} (缺失)")

            # 如果指定了输出文件，进行完整重建
            if output_file:
                print(f"\n开始完整重建...")

                if not rebuilder.rebuild():
                    print("❌ 完整重建失败")
                    return False

                # 获取重建数据
                rebuilt_data = rebuilder.get_rebuilt_data()
                if not rebuilt_data:
                    print("❌ 无法获取重建数据")
                    return False

                # 写入输出文件
                try:
                    with open(output_file, 'wb') as f:
                        f.write(rebuilt_data)
                    print(f"✓ 重建文件已保存: {output_file} ({len(rebuilt_data)} 字节)")

                    # 基本验证
                    if rebuilt_data[:4] == b'\x7fELF':
                        print("✓ 输出文件ELF头部验证通过")
                    else:
                        print("❌ 输出文件ELF头部验证失败")

                except Exception as e:
                    print(f"❌ 保存输出文件失败: {e}")
                    return False

            return True

    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    if len(sys.argv) < 3:
        print("用法:")
        print(f"  {sys.argv[0]} <input_so> <dump_base_addr> [output_so]")
        print()
        print("示例:")
        print(f"  {sys.argv[0]} dumped.so 0x7DB078B000")
        print(f"  {sys.argv[0]} dumped.so 0x7DB078B000 fixed.so")
        sys.exit(1)

    input_file = sys.argv[1]
    try:
        dump_base_addr = int(sys.argv[2], 0)  # 支持0x前缀
    except ValueError:
        print(f"❌ 无效的基地址格式: {sys.argv[2]}")
        sys.exit(1)

    output_file = sys.argv[3] if len(sys.argv) > 3 else None

    if not os.path.isfile(input_file):
        print(f"❌ 输入文件不存在: {input_file}")
        sys.exit(1)

    print("Python版本ELF重建测试")
    print("=" * 80)

    success = test_section_creation(input_file, dump_base_addr, output_file)

    if success:
        print("\n🎉 测试完成！")
        sys.exit(0)
    else:
        print("\n💥 测试失败！")
        sys.exit(1)

if __name__ == '__main__':
    main()
