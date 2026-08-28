# 文档与实验记录标准

## 基本原则

- 语言规则（全程中文）见 `SKILL.md` 速查清单第1条。
- 边分析边写，不在分析结束后凭记忆补。
- 不覆盖旧记录，不删除失败轮次。
- 每轮记录必须能让后来接手的人复现分析路径：写清分析思路、所用工具、实际命令、代码改动、实验结果和下一步计划。
- 所有已经分析出来的检测代码都必须记录，不要遗漏细节；检测代码较长时可放到独立小节或产物文件，并在本轮记录中写明路径、函数、offset 和摘要。

## 统一记录格式

每轮实验必须记录以下 10 项：

- **记录时间**：本轮记录的时间。
- **分析思路**：为什么这样分析、当前假设、依据来自哪些日志/导出/历史记录、要验证或排除什么。
- **本轮操作**：实际执行的操作、脚本或分析动作。
- **操作目的**：本轮目的、触发原因或要验证的判断。
- **所用工具**：工具名称、版本/路径（已知时）、设备侧组件、脚本或插件来源；没用工具写“无”。
- **运行命令**：实际运行的命令、关键参数、工作目录、目标进程/so/函数；没有运行命令写“无”。
- **代码变更**：改动的文件、脚本、offset、patch 语义；没有改动写“无”。
- **检测代码明细**：完整记录所有已分析出的检测代码，包括 so/函数/offset、反编译伪代码或关键汇编、判断条件、常量/字符串、syscall/API、返回值/状态码、fatal/kill/abort/BRK 分支、上下游调用和证据路径；还没确认写“待静态分析”。
- **实验结果**：成功/失败、关键现象、关键证据位置或结论。
- **下一步计划**：下一步动作、需要补的静态分析或验证。

示例：

```markdown
## 2026-06-22 14:30

- 记录时间：2026-06-22 14:30
- 分析思路：同一检测链动态失败已到 3 次，先确认是否存在匿名 RX 执行，再决定是否继续分析磁盘 so。
- 本轮操作：dump `libDexHelper.so` 并检查运行期 maps 中的匿名可执行段。
- 操作目的：同一检测链动态失败已到 3 次，需要转入 so 和匿名段静态分析。
- 所用工具：MemDumper、xiaojianbang-syscall-filter、rizin（待导出）。
- 运行命令：`adb shell su -c './memdumper -p <pid> -l -n libDexHelper.so'`；`adb shell su -c 'cat /proc/<pid>/maps' > artifacts/maps/pid_maps.txt`。
- 代码变更：无。
- 检测代码明细：待静态分析；当前只确认存在 `[anon:.bss] rwx`，崩溃 `pc=0x55f60` 需要归属到 dump 产物或匿名段后再记录完整函数、分支和 fatal 调用。
- 实验结果：发现 `[anon:.bss] rwx`，dump 已保存到 `artifacts/dumps/...`；rizin 尚未确认函数范围。
- 下一步计划：用 rizin 导出 dump 产物，确认 `0x55f60` 所在函数范围并检查 CRC 分支。
```

## 细节放置规则

- so、函数、patch、验证、匿名段、CRC 等细节都写进上述 10 项；不强制维护独立 per-so 表、per-function 表或 patch 表，但不得因此省略检测代码细节。
- 关键证据写最短可定位信息，例如日志路径、tombstone 名称、偏移、函数名或产物路径；不要贴大段无关日志。
- 必须区分“已确认 / 推测 / 未确认 / 待验证”，但用一句话写在“实验结果”或“下一步计划”里即可。
- 检测代码明细必须覆盖已分析出的全部检测相关逻辑：`if/else`、返回值、fatal 分支、CRC/maps/ptrace/syscall 判断、字符串/常量、调用链和 patch 候选。只省略与检测无关的长反编译或重复日志。
- 用户明确要求详细报告、交接文档或表格时，才额外展开。

## Patch 归属与崩溃原因记录要求

涉及崩溃后 patch、系统 so 调用栈、匿名段检测或 `<shell_so>` 检测时，除统一 10 项外必须补齐：

- **patch ownership**：patch 目标归属，写明 `<shell_so>`、目标业务 so、匿名段、memfd、目标控制 wrapper 或系统库症状点。
- **crash classification**：崩溃分型，区分检测自杀、故意空指针、payload/descriptor 缺失、前序 patch 诱发、layout/ABI 不匹配、系统生命周期和普通崩溃。
- **null pointer source**：若为空指针，记录空值来源、首次变空位置、上游写入者、下游使用者和是否由 patch 引入。
- **system-so boundary**：若调用栈进入 `libc.so`、`libart.so`、linker，记录为什么它是症状点还是真实目标控制点。
- **rollback evidence**：回退相关 patch 后的对照结果。

## Metadata / Payload 记录要求

涉及 OAT/VDEX/DEX、qh/pk/lm、自定义 marker、APK 尾部 payload、synthetic descriptor、fake dex、pseudo dex、metadata replacement 或 OAT/Dex redirect 时，除统一 10 项外，必须在“检测代码明细 / 实验结果 / 下一步计划”中补齐以下字段：

- **metadata source**：metadata 来自 APK entry、APK tail、odex/vdex/dex、assets、匿名内存、解密缓存还是 synthetic buffer；记录路径、entry、offset、长度和证据命令。
- **descriptor layout**：descriptor 对象字段表，至少写明关键偏移、值、来源和用途，例如 descriptor_len、payload offset、count、entry 起点、key/hash 字段、`obj+8`、`obj+0xc` 等。
- **payload source**：真实 payload 的来源、提取方式、是否压缩/加密、解密/解压入口和固化产物路径；未找到时明确写“未确认”，不能用空 descriptor 替代。
- **asset path/hash/length**：固化 payload 资产的相对路径、长度、sha256、前缀字节和生成命令。
- **downstream consumer**：消费 descriptor/payload 的函数、offset、循环或 `memcpy/memmove` 位置，以及它读取哪些字段。
- **target guard**：命中目标、允许规则、拒绝规则、拒绝原因和回退行为；system/framework/bootclasspath/apex OAT 必须有拒绝记录。
- **no-payload control**：移除或置空 payload 的对照实验结果，用于证明崩溃是否由 payload 缺失导致。
- **rollback control**：回退 synthetic descriptor、redirect 或 metadata replacement 后的结果，用于确认 patch 归因。

payload asset 固化规范：

- payload 二进制保存为 `.bin`，同目录保存同名 `.json` manifest。
- manifest 至少包含：`source_path`、`source_entry`、`source_offset`、`source_length`、`sha256`、`prefix_hex`、`descriptor_layout`、`key_fields`、`count`、`entry_chain`、`consumer_offsets`、`target_guard`、`created_at`。
- 若 payload 来自运行期内存，manifest 还要记录 pid、maps 范围、base、dump 命令、对齐/fix 口径和原始 dump hash。
- 若 payload 是合成或拼接结果，manifest 必须记录每段来源、拼接顺序、填充值、生成脚本路径和输入 hash。
