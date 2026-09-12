# 风控特征对照（防守方视角 ↔ 逆向检测）

> 数据源：本技能内 `references/risk-control-data/data/knowledge/*.json`（已入库，自包含）
> - 知识层：`references/risk-control-data/data/knowledge/<主题>.json`（手工维护，唯一编辑处）
> - 结构：每字段含 `risk`(风控为何采)、`detect`(怎么采)、`anomaly`(异常判据)、`spoof`(怎么对抗)、`links`；每规则含 `id/name/level/action/logic/expr/fields`。
> - 检索：按主题文件（01-12）覆盖自动化/网络/模拟器/完整性/身份/Hook调试/传感器/QEMU/ROM/行为习惯等。
> 本文只做**逆向最相关**的精炼对照，完整 855 字段 / 75 规则以 `data/knowledge/*.json` 为准。

## 一、定位

风控特征库是「防守方」事实库：记录风控**采什么字段、怎么判异常、怎么处置**。逆向时遇到某个检测，来这里反查「风控侧是怎么定义和处置它的」，得到：

- `detect`：风控从哪些 API / syscall / /proc 拿数据 → 反推 App 会在哪做检测、怎么查。
- `anomaly`：异常判据（阈值/组合）→ 精确知道要骗过哪些条件。
- `expr`：规则表达式草案 → 风控判定的可执行逻辑。
- `spoof`：黑产/逆向通常怎么对抗 → 理解"为什么风控要这样防、还能怎么绕过"。

## 二、主题 ↔ 逆向检测 对照

| 风控主题（knowledge 文件） | 对应逆向检测（壳特征库/流程） |
|---|---|
| `04-integrity.json` 系统完整性 | CRC/完整性校验、APK 签名、ROM 一致性、root |
| `06-hook-debug.json` Hook/调试 | 反 Hook、反调试、Frida/Xposed、TracerPid、匿名 RWX |
| `03-emulator.json` 模拟器 | 模拟器/QEMU/云手机检测 |
| `07-sensor.json` 传感器 | 云手机/模拟器物理约束（传感器噪声、采样间隔） |
| `02-network.json` 网络 | 代理/VPN/秒拨/机房出口 |
| `05-identity.json` 身份 | 设备指纹/改机重置 |
| `01-automation.json` 自动化 | 群控/脚本/无障碍/自动点击 |
| `09-rom-integrity.json` ROM 一致性 | 自编译 ROM/KernelSU/内核指纹 |
| `08-qemu-detail.json` QEMU 细节 | QEMU 属性/文件/设备节点 |
| `10-behavior-habit.json` 行为习惯 | 页面/交易/注册/登录行为画像（服务端侧为主） |

## 三、逆向最相关精华（可直接对照用）

### Hook/调试（`06-hook-debug.json`）
- **核心规则 R-HOOK-001「运行时注入」**：`maps_hook_hit OR method_native_flag_hit OR dual_path_mismatch_cnt >= 1`。
  - 对应壳特征库：特征 7 inline hook 检测、特征 8 Frida 痕迹、特征 4/5 自解析。
  - 风控侧还强调「**先于所有其他规则生效**」——注入成立时其余字段都不可信。逆向同理：先确认是否被 hook，再谈其它检测。
- **Frida 检测字段**：默认端口 27042/27043；线程名 gmain/gum-js-loop/pool-frida；maps 找 frida-agent 与匿名可执行段；fd 指向可疑文件。`spoof`：改端口/改线程名/gadget 静态注入可绕过，故风控加**匿名 rwx 段扫描 + GOT/PLT 完整性校验**。
- **内存作弊 R-DEBUG-003**：`code_crc_mismatch OR anon_rwx_seg_cnt > 0 OR memtool_proc_hit`。
  - 正好对应流程 §5 匿名内存硬门禁、§9 CRC/完整性校验。
- **栈回溯 isNative**：Java 方法被 Hook 后 accessFlags 含 ACC_NATIVE、栈出现 LSPHooker_/proxy 帧——**不依赖特征串的通用检测**。
- **检测位置**：核心检测须下移 native + syscall 直读 /proc + 自身 so CRC + GOT/PLT 校验 → 对应「syscall 走指针表/自建符号表」的防守侧动机。

### 完整性（`04-integrity.json`）
- **R-TAMPER-001 信任链破坏**：`vbmeta_device_state='unlocked' OR veritymode!='enforcing' OR build_tags~'test-keys'`。
- **R-TAMPER-002 客户端重打包**：`signature_sha256 != expected OR source_dir NOT LIKE '/data/app/%' OR so_integrity_failed`。
- **R-TAMPER-003 ROM 属性不自洽**：`fingerprint_java != fingerprint_prop OR fingerprint_segment_mismatch OR fingerprint NOT IN device_db`。
  - 关键思想：**双路取值比对**（Java vs native / getprop vs build.prop），Hook 常只改一路 → 对应「复合条件一起改、多路一致性」。
- **R-TAMPER-004 Root**：`su_path_hit OR selinux_status!='enforcing' OR magisk_feature_hit`。note：root 用户多，宜"限制"而非"直接封"。

### 模拟器（`03-emulator.json`）
- **核心思想**：不找特征串，查**硬件自洽性**——CPU/GPU/传感器/输入设备互相矛盾才定性（如骁龙 SoC 却报 Mali GPU、8 核全同频、仅加速度计）。
- **R-EMU-001**：`qemu_prop_hit OR gl_renderer ~ 'Swiftshader|llvmpipe|VirGL|Bluestacks'`（零误伤级）。
- **R-EMU-004 CPU 信息被改写**：`cpuinfo_midr_mismatch OR core_cnt_java != core_cnt_sysfs`（/proc/cpuinfo 文本 vs /sys midr_el1 寄存器值比对）。

## 四、维护方法（遇到新检测怎么加）

1. 编辑 `references/risk-control-data/data/knowledge/<主题>.json`，按模板给字段补 `risk/detect/spoof/anomaly/links`，给规则补 `expr/logic/fields`。
2. JSON 即直接可读数据，无需构建；后续如需可视化，再单独建独立查看器（本技能不随附 web 前端）。

## 五、逆向流程怎么用（挂钩点）

- 进 so 静态分析前、判断某 so 是"壳/检测"时：先查本文第三节对应主题，确认**风控侧如何定义这个检测**（`detect`+`anomaly`+`expr`），再针对性逆向。
- §9 CRC/完整性校验：对照 `04-integrity` + `R-TAMPER-*`，看风控侧判据（vbmeta/veritymode/test-keys/签名/双路取值）。
- §5 匿名内存：对照 `R-DEBUG-003`（anon_rwx_seg_cnt）。
- 壳特征库对应特征（7/8/9/11/16）也挂了交叉引用，见 `shell-signatures.md`。
