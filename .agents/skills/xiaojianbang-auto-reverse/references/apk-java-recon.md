# APK/Java 前置分析

> 语言规则（全程中文）见 `SKILL.md` 速查清单第1条。本文件是完整逆向流程的**前置段**——从拿到 APK，到锁定真正值得逆的 native `.so` 为止。**native 深度分析分支**（检测链、加密壳 dump/fix、syscall 定位、OLLVM、CRC、patch、验证）见 `workflow-standards.md` §0-§13 与 `SKILL.md` 强约束速查清单第1-24条，不在本文件展开。

## 定位

逆向目标常常不是"上来就啃 `.so`"；多数任务是从 APK 与 Java 层起步，逐层收敛到"哪些 native 库承载了检测/加固/算法"。本文件把这段前置流程做扎实，并明确**什么时候该进入 native 分支、什么时候在上层收尾**。工具在各阶段**按方法论发现**（候选 + 按目标实际命中），版本/路径以 `environment.md` 环境事实为准，不在此写死。

## 目录

- 步骤A. 目标与授权确认
- 步骤B. APK 信息收集（解包 / 清单 / 组件 / 入口 / 壳特征）
- 步骤C. Java/DEX 静态分析（首选 garlic，回退 jadx-cli）
- 步骤D. 行为观察（动态，可选）
- 步骤E. native 库发现
- 交接：进入 native 分支 vs 收尾

## 步骤A. 目标与授权确认

- **目的**：锁定分析对象并确认边界与授权。
- **看什么**：目标 App 包名/进程/版本、core dump、崩溃日志、样本来源；是否自有或用户明确许可。
- **工具（候选）**：`adb` 看包名/进程、文件系统浏览样本。
- **门禁**：只做自有或用户明确许可的样本/研究/调试环境；边界不清先说明并停止未授权访问、隐蔽控制、数据外传。涉及新 `.so` 工具逆向且用户未明确授权直接分析时，先走 `safety-and-confirmation-rules.md` 的确认流程。
- **产物**：目标描述、授权结论、工作目录、稳定复现命令（启动 App / 触发崩溃 / 采样）。

## 步骤B. APK 信息收集（解包 / 清单 / 组件 / 入口 / 壳特征）

- **目的**：摸清 APK 的"头"——包名、版本、权限、组件、入口、壳与加固特征。这一步决定后面的分析方向。
- **看什么**：
  - `application`/`android:name`（是否为壳入口）、`versionName`/`versionCode`、`minSdk`/`targetSdk`。
  - 权限（读/写/网络/root 相关）、`uses-library`。
  - 组件（Activity/Service/Receiver/Provider）及其 `exported`、`launchMode`、入口 Activity / Application。
  - DEX 是否加密、加固壳特征（Application 是否为壳 wrapper、多 DEX、`assets` 里的可疑加密 APK/DEX）。
  - 签名方式（v1/v2/v3）、`nativeLibraryDir`、打包的 `.so` 清单。
- **工具（候选）**：`aapt2 dump badging` / `aapt`、`apktool d`、`7z`，或用 `jadx-cli` 直接开 APK 看 manifest 与源码。按目标命中为准。
- **产物**：manifest 摘录、组件/入口表、加固与 native 依赖初判。

## 步骤C. Java/DEX 静态分析（首选 garlic，回退 jadx）

- **目的**：进入 native 前先回答"这个 App 到底干什么、值不值得逆 native"。这是**方向前哨**——方向错了，后续 native 分析都会偏。
- **工具（硬约束）**：Java/Kotlin 层首选 `garlic`（C 实现、秒级，无需关 checksum）。`garlic` 未安装/找不到/不可用时回退 `jadx`（CLI，调用必须带 `-Pdex-input.verify-checksum=no`），并记录回退原因。完整条款见 `tooling-and-paths.md`。
- **看什么**：
  - 入口启动链：`Application.onCreate`、入口 `Activity.onCreate`、`MainActivity`、`Service`/`Receiver` 入口。
  - native 边界：`System.loadLibrary`/`System.load` 调用点；`native` 方法声明清单；这些 native 方法如何绑定（`JNI_OnLoad` 里 `RegisterNatives`，或方法名/签名约定映射）。
  - 调用图：从入口往下追，标注 native 边界；找到关键功能类、网络 endpoint、字符串/常量、加密/算法/签名校验相关类。
  - 壳/加固：DEX 是否由壳在运行时解密加载、Application 是否为壳代理、是否走自定义 `ClassLoader`。
- **产物**：入口调用链、native 方法清单 + 绑定关系、关键功能/算法/检测相关类清单、"是否值得逆 native"的判定与理由。
- **分流**：确认目标只是纯 Java/网络/资源逻辑 → 到此收尾；命中 native 检测/壳化/算法/性能/加固 → 继续步骤 D-E。

## 步骤D. 行为观察（动态，可选）

- **目的**：用运行期行为佐证步骤C 的静态结论，明确 native 库的加载时机与触发条件。
- **看什么**：启动后加载了哪些 `.so` 及顺序；崩溃/闪退点与信号；网络/加密握手；是否有自解密、运行时重建迹象。
- **工具（候选，按需求用才检查前置）**：`adb` 启动与 `logcat`、Frida（使用前必须先确认 frida-server——见 `workflow-standards.md` §2/§11）、`eCapture`（TLS）、`xiaojianbang-syscall-filter`、内存 dump。
- **产物**：so 加载序列、行为日志、崩溃证据、触发条件。

## 步骤E. native 库发现

- **目的**：从 APK、运行期 `maps`、`System.loadLibrary`、`lib/*` 收敛出**真正需要分析**的 native 库，并对"是否值得逆"、是否壳化/加密做初判。
- **做法**：
  - 汇总 so 清单：打包在 APK `lib/` 的、运行期 `maps` 加载的、代码里 `System.loadLibrary` 的。
  - 对每个 so 初判：导出符号、`JNI_OnLoad`/constructor、大小、section table/字符串表是否异常、是否加密/壳化/自解密、是否与步骤C 的 native 方法或检测逻辑对应。
  - 标注"主分析对象"（真正承载检测/算法/加固的 so）与"伴随 so"。
- **工具（候选）**：`rizin`/`rz-bin`、`readelf`、jadx。深度分析进 native 分支用 `rizin_export.py` + Ghidra 回退。
- **产物**：so 清单 + 每 so 的"是否值得逆"初判 + 加密/壳化嫌疑标记。

## 交接：进入 native 分支 vs 收尾

- **进入 native 分支**：步骤B-E 确认目标涉及 native 检测链、壳化/加密、算法还原、崩溃归属、性能或加固——值得钻 `.so`。此时按 `workflow-standards.md` §0-§13 与 `SKILL.md` 强约束第1-24条原样执行：
  - 工具路线先按 §9.0 按任务类型决策（过检测 vs 分析算法）。
  - 加密/壳化 `.so` 必须先 dump/fix（§4），禁止直接分析磁盘 so。
  - 闪退/崩溃必须先走 syscall-filter（§3）与匿名内存检查（§5）。
  - 静态分析强制顺序（§7）、函数范围（§6）、混淆（§8）、CRC（§9.1/§9.2）、patch 归属与崩溃分型（§10）、验证闭环（§11）、壳 metadata contract（§12/§13）。
- **收尾**：静态与行为证据都指向纯 Java/网络逻辑，或无必要分析 native → 说明理由并走验证/实验记录收尾（`documentation-standards.md`、`verification-checklists.md`），不硬啃 `.so`。
