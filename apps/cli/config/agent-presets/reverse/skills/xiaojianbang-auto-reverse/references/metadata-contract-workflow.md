# Metadata Contract 工作流

适用于 OAT/VDEX/DEX parser、qh/pk/lm、自定义 marker、APK 尾部 payload、synthetic descriptor、fake dex/pseudo dex、metadata replacement 和 OAT/Dex redirect。目标是区分“早期结构检查通过”和“下游语义 payload 完整”，避免把后续崩溃误判成新的检测点。

## 目录

- 1. 识别 producer / source
- 2. 恢复早期 contract
- 3. 追踪下游 consumer
- 4. 找真实 payload source
- 5. 固化 payload asset
- 6. 加 target guard
- 7. patch 归因矩阵
- 8. 验证与回退
- 9. 反模式

## 1. 识别 producer / source

先找 metadata 或 descriptor 的生产者，而不是先 patch 崩溃点：

- 文件来源：APK entry、APK tail、assets、odex/vdex/dex、oat、壳私有容器。
- 内存来源：匿名 RX/RW、memfd、解密缓存、运行期重建 buffer。
- 合成来源：runner、Frida 脚本、patch 后构造的 synthetic descriptor。
- 记录 source path/entry/offset/length/sha256、读取函数、解密/解压入口和写入 descriptor 的函数 offset。

如果 source 尚未确认，只能补证据；不要用空 qh、零 entry 或常量 buffer 当稳定方案。

## 2. 恢复早期 contract

恢复 parser 早期检查需要的结构字段：

- magic/marker、版本、bounds、alignment、descriptor_len。
- payload offset、payload length、count、entry start、key/hash 字段。
- 对象写入偏移，例如 `obj+8`、`obj+0xc`、`D+0x20`、`D+0x68`、`D+0x6c`、`D+0x70`。

早期 contract 通过只代表 parser 不会在 marker/bounds 阶段失败。必须在记录里明确写“早期 contract 已满足”，但不能据此宣布绕过完成。

典型信号：zero-entry descriptor 能通过早期检查，例如 `0x58d59/0x1cef8` 一类 parser 分支，但后面崩在 `<shell_so>+0xda44` 这类壳 so 偏移。这通常说明壳接受了 descriptor 外形，但下游缺少真实 payload。

## 3. 追踪下游 consumer

从早期 parser 继续跟到所有消费者：

- `memcpy/memmove`、entry loop、hash/key 比对、解密/解压调用。
- dex begin / oat begin / vdex begin 计算。
- VM wrapper、loader、JNI bridge、OatDexFile consumer。
- 读取 count、entry chain、payload pointer、payload length 的位置。

每个 consumer 记录函数、offset、读取字段、字段来源和失败分支。若 consumer 需要 `qh+0xc`、entry blob、count 或 key table，synthetic descriptor 必须提供真实数据；只让上游返回 clean 不够。

## 4. 找真实 payload source

下游 consumer 需要 blob/count/entries 时，必须找到真实 payload：

- APK tail：检查 EOCD 之后、zip comment、非标准尾部块。
- APK entry/assets：按 entry 名、压缩方式、offset、长度定位。
- odex/vdex/oat：确认版本 layout、record offset、dex begin 口径。
- 匿名内存或 memfd：用 maps/syscall-filter 定位并 dump/fix。
- 解密缓存：跟踪解密函数输出 buffer 和长度。

找不到 payload 时，结论应是“descriptor 早期 contract 可合成，但语义 contract 未完成”。不要继续 patch `memmove`、VM wrapper 或 parser helper。

## 5. 固化 payload asset

稳定方案必须把 payload 固化成可复现资产：

- 保存 `.bin`：原始 payload 或完整合成后的 payload。
- 保存 `.json` manifest：记录 `source_path`、`source_entry`、`source_offset`、`source_length`、`sha256`、`prefix_hex`、`descriptor_layout`、`key_fields`、`count`、`entry_chain`、`consumer_offsets`、`target_guard`、`created_at`。
- 若是运行期 dump，manifest 增加 pid、maps 范围、base、dump 命令、fix 口径和原始 dump hash。
- 若是拼接或补齐，manifest 增加每段来源、填充值、生成脚本路径和输入 hash。

示例字段关系只能作为记录格式参考，实际值必须来自目标样本证据：`D+0x20 = descriptor_len`、`D+0x68 = 0`、`D+0x6c = 0x70`、`D+0x70 = complete qh tail`、`qh+8 = 0x38c`、`count = 7`。

## 6. 加 target guard

OAT/Dex redirect 或 metadata replacement 必须有 target guard：

- 允许规则：目标包名、目标 APK/odex/vdex/dex 路径、entry 名、长度、hash、base odex 特征。
- 拒绝规则：system/framework/bootclasspath/apex OAT、非目标包路径、hash/长度不匹配、未知来源。
- 拒绝时记录 reason，例如 `not_target_app_base_odex`。
- guard 命中和拒绝都写入实验记录；不允许静默把 redirect 应用到系统 OAT。

高版本 OAT 先确认 layout。若旧 parser 把 `apex`、`bootclasspath` 等 ASCII 当 offset，优先按 layout mismatch 处理。版本阈值 patch 只能作为 blocker probe，最终方案要补 layout 解析、payload contract 或有 guard 的重定向。

## 7. Patch 归因矩阵

验证复杂方案时按矩阵归因，不要只测最终组合：

- `all_current`：当前完整方案。
- `no_patches_all`：全部 patch 移除。
- `no_shell_so_patches`：移除 `<shell_so>` / 目标壳 so 相关 patch，仅保留非壳辅助项。
- `guard_only`：只启用 target guard/过滤，不替换 payload 或 descriptor。
- `without_each_patch`：逐个移除每个 patch。
- `probe_only`：只启用版本阈值、日志或非语义探针。
- `compatibility_shim_only`：只启用 layout/兼容 shim。

每项记录首个失败点、signal、fault addr、pc/lr、activity 是否到达、是否 `JNI_ERR`、是否 fatal、是否新增 ANR 或卡顿。

## 8. 验证与回退

完成方案前必须验证：

- descriptor ack 或等价命中证据存在。
- payload length/hash/prefix/count 与 manifest 一致。
- 下游 consumer cleanly reached，且不再因 payload 缺失崩到 `memcpy/memmove`、VM wrapper、loader 或 helper。
- target guard 命中目标、拒绝非目标并记录 reason。
- no-payload control 能复现 payload 缺失失败。
- rollback control 能回到旧行为，证明当前 patch 的因果关系。
- App 可交互，无 target fatal、无明显 ANR、无高频异常日志。

## 9. 反模式

- 不要把下游崩溃点直接当检测点；先确认是否是 synthetic descriptor 缺 payload。
- 不要直接 patch VM wrapper、`memmove` 或通用 parser helper 来掩盖 contract 缺失。
- 不要把版本阈值 patch 当最终 patch；它只能证明 blocker 位置。
- 不要静默把 OAT/Dex redirect 应用到 system/framework/bootclasspath/apex 产物。
- 不要只记录“qh 已补”或“descriptor 已通过”；必须写明 payload source、entry count、consumer 和 target guard。
