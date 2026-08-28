#!/usr/bin/env python3
"""
验证Python版本ELF重建修复效果
================================

这个脚本验证修复后的Python版本是否能正确生成段头表，
特别是检查.text&ARM.extab和.data段是否正确创建。
"""

import sys
import os
import logging

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sofixer.elf_reader import ObfuscatedELFReader
from sofixer.elf_rebuilder import ELFRebuilder

# 设置简洁的日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

def validate_section_headers(rebuilder):
    """验证段头表是否正确创建"""
    print("\n=== 段头表验证 ===")

    expected_sections = {
        '.dynsym': 11,      # SHT_DYNSYM
        '.dynstr': 3,       # SHT_STRTAB
        '.hash': 5,         # SHT_HASH
        '.plt': 1,          # SHT_PROGBITS
        '.text&ARM.extab': 1,  # SHT_PROGBITS
        '.data': 1,         # SHT_PROGBITS
        '.shstrtab': 3      # SHT_STRTAB
    }

    found_sections = {}
    issues = []

    # 遍历所有段头
    for i, shdr in enumerate(rebuilder.section_headers):
        # 获取段名
        if shdr['sh_name'] < len(rebuilder.shstrtab):
            name_start = shdr['sh_name']
            name_end = rebuilder.shstrtab.find(0, name_start)
            if name_end == -1:
                name_end = len(rebuilder.shstrtab)
            name = rebuilder.shstrtab[name_start:name_end].decode('utf-8', errors='ignore')
        else:
            name = f"<invalid:{shdr['sh_name']}>"
            issues.append(f"段 {i}: 无效的段名偏移量 {shdr['sh_name']}")
            continue

        if name in expected_sections:
            found_sections[name] = shdr

            # 验证段类型
            expected_type = expected_sections[name]
            if shdr['sh_type'] != expected_type:
                issues.append(f"段 '{name}': 类型错误，期望 {expected_type}，实际 {shdr['sh_type']}")

            # 验证关键段的特定属性
            if name == '.text&ARM.extab':
                if shdr['sh_flags'] != 0x6:  # SHF_ALLOC | SHF_EXECINSTR
                    issues.append(f"段 '{name}': 标志错误，期望 0x6，实际 0x{shdr['sh_flags']:x}")
                if shdr['sh_size'] == 0:
                    issues.append(f"段 '{name}': 大小为0，可能计算错误")

            elif name == '.data':
                if shdr['sh_flags'] != 0x3:  # SHF_ALLOC | SHF_WRITE
                    issues.append(f"段 '{name}': 标志错误，期望 0x3，实际 0x{shdr['sh_flags']:x}")
                if shdr['sh_size'] == 0:
                    issues.append(f"段 '{name}': 大小为0，可能计算错误")

    # 检查缺失的段
    for expected_name in expected_sections:
        if expected_name not in found_sections:
            issues.append(f"缺失段: {expected_name}")

    # 报告结果
    print(f"找到关键段: {len(found_sections)}/{len(expected_sections)}")
    for name, shdr in found_sections.items():
        print(f"  ✓ {name:<20} 类型={shdr['sh_type']:<2} 地址=0x{shdr['sh_addr']:<10x} 大小=0x{shdr['sh_size']:<8x}")

    if issues:
        print(f"\n发现问题 ({len(issues)}):")
        for issue in issues:
            print(f"  ❌ {issue}")
        return False
    else:
        print("\n✅ 段头表验证通过")
        return True

def validate_addressing(rebuilder):
    """验证地址计算是否正确"""
    print("\n=== 地址计算验证 ===")

    issues = []
    so_info = rebuilder.so_info

    # 检查基本地址字段
    if not hasattr(so_info, 'min_load') or so_info.min_load is None:
        issues.append("min_load 未设置")
    if not hasattr(so_info, 'max_load') or so_info.max_load is None:
        issues.append("max_load 未设置")
    if not hasattr(so_info, 'pad_size'):
        issues.append("pad_size 未设置")

    if not issues:
        print(f"  ✓ 最小加载地址: 0x{so_info.min_load:x}")
        print(f"  ✓ 最大加载地址: 0x{so_info.max_load:x}")
        print(f"  ✓ 填充大小: {so_info.pad_size} 字节")

        # 验证max_load > min_load
        if so_info.max_load <= so_info.min_load:
            issues.append(f"max_load ({so_info.max_load:x}) 应该 > min_load ({so_info.min_load:x})")

        # 检查.data段大小是否使用了正确的max_load
        data_sections = [shdr for shdr in rebuilder.section_headers
                        if shdr['sh_name'] < len(rebuilder.shstrtab)]

        for shdr in data_sections:
            name_start = shdr['sh_name']
            name_end = rebuilder.shstrtab.find(0, name_start)
            if name_end == -1:
                name_end = len(rebuilder.shstrtab)
            name = rebuilder.shstrtab[name_start:name_end].decode('utf-8', errors='ignore')

            if name == '.data':
                expected_size = so_info.max_load - shdr['sh_addr']
                if shdr['sh_size'] != expected_size:
                    issues.append(f".data段大小计算错误: 实际={shdr['sh_size']:x}, 期望={expected_size:x}")
                else:
                    print(f"  ✓ .data段大小计算正确: 0x{shdr['sh_size']:x}")
                break

    if issues:
        print(f"\n发现问题 ({len(issues)}):")
        for issue in issues:
            print(f"  ❌ {issue}")
        return False
    else:
        print("\n✅ 地址计算验证通过")
        return True

def validate_string_table(rebuilder):
    """验证字符串表是否正确"""
    print("\n=== 字符串表验证 ===")

    # 检查字符串表内容
    expected_names = ['.dynsym', '.dynstr', '.hash', '.plt', '.text&ARM.extab', '.data', '.shstrtab']
    found_names = []

    # 解析字符串表
    i = 1  # 跳过第一个null字节
    while i < len(rebuilder.shstrtab):
        start = i
        while i < len(rebuilder.shstrtab) and rebuilder.shstrtab[i] != 0:
            i += 1
        if start < i:
            name = rebuilder.shstrtab[start:i].decode('utf-8', errors='ignore')
            found_names.append(name)
        i += 1  # 跳过null终止符

    print(f"字符串表内容: {found_names}")

    missing_names = [name for name in expected_names if name not in found_names]
    if missing_names:
        print(f"❌ 缺失段名: {missing_names}")
        return False
    else:
        print("✅ 字符串表验证通过")
        return True

def main():
    if len(sys.argv) != 3:
        print("用法: python validate_fix.py <input_so> <dump_base_addr>")
        print("示例: python validate_fix.py dumped.so 0x7DB078B000")
        sys.exit(1)

    input_file = sys.argv[1]
    try:
        dump_base_addr = int(sys.argv[2], 0)
    except ValueError:
        print(f"❌ 无效的基地址: {sys.argv[2]}")
        sys.exit(1)

    if not os.path.isfile(input_file):
        print(f"❌ 文件不存在: {input_file}")
        sys.exit(1)

    print("Python版本ELF重建修复验证")
    print("=" * 50)
    print(f"输入文件: {input_file}")
    print(f"基地址: 0x{dump_base_addr:x}")

    try:
        # 加载和重建
        with ObfuscatedELFReader(input_file) as elf_reader:
            elf_reader.set_dump_base_addr(dump_base_addr)

            if not elf_reader.load():
                print("❌ ELF文件加载失败")
                return False

            rebuilder = ELFRebuilder(elf_reader)

            if not rebuilder.extract_so_info():
                print("❌ soinfo提取失败")
                return False

            if not rebuilder._rebuild_section_headers():
                print("❌ 段头表重建失败")
                return False

            # 运行验证
            all_passed = True
            all_passed &= validate_string_table(rebuilder)
            all_passed &= validate_section_headers(rebuilder)
            all_passed &= validate_addressing(rebuilder)

            if all_passed:
                print("\n🎉 所有验证通过！修复成功！")
                print("\n修复要点:")
                print("  ✓ 添加了pad_size计算和max_load调整")
                print("  ✓ 修复了.data段大小计算")
                print("  ✓ 完善了段地址排序和链接")
                print("  ✓ 改进了字符串表管理")
                return True
            else:
                print("\n💥 验证失败，仍需修复")
                return False

    except Exception as e:
        print(f"❌ 验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
