# 壳特征库（壳特定手法 → 快速匹配 → 应对）

> 本文是可检索的「加固壳/反调试 so 特征指纹库」。逆向时遇到下列特征之一，可快速匹配到对应应对思路，便于沿用同类壳的过法。
> 来源：实战文章《对某学习APP的frida检测绕过》(看雪 292547) 提炼 + 通用反调试/加固壳套路。按「特征 → 是什么 → 怎么识别 → 怎么应对」组织。

---

## 使用方式（先判断命中哪些特征）

1. 拿到目标 so / 检测链后，先粗扫下列特征（字符串、导入表、动态段、反编译、运行时行为）。
2. 命中某特征 → 跳到对应条目，按「怎么识别」核对，再按「怎么应对」推进。
3. 特征可叠加（一个壳常有多个特征），逐个匹配、逐个过，不能只处理一个就收工。
4. 每版壳/每加固商特征可能随版本变化；「应对」是通用的，具体地址/函数名以目标样本为准。

---

## 特征 1：SMC / 自解密 so（磁盘乱码，运行时才解密）

- **是什么**：so 在磁盘上是加密乱码，运行时才在内存里解密/重建为可执行代码。
- **怎么识别**：直接反编译磁盘 so 出不来有效代码；`rz-bin -I`/`file` 显示 bintype/class 正常但段表/程序头/字符串表异常；rizin 只识别导入桩或少量函数、无有效 `.text`；运行 pc/lr 不落在磁盘可解释代码；constructor/JNI_OnLoad 申请匿名 RX 并解密。
- **应对（dump/fix 硬门禁）**：
  1. 必须**运行时 dump** 真实镜像 + 修复，禁止直接分析磁盘 so 下结论 / 给 patch。
  2. dump 时机权衡：越晚越完整（解密全）、越晚越危险（开始检测+杀）。constructor 短窗口/快速闪退用 `frida_memdump_so.py`，稳定进程用 `memdump_so.py`。
  3. `--raw`/syscall/手工 dump 拿回的是畸形 ELF → 宿主机 **SoFixer**（`sofixer_run.py`，`-m` 必须 = dump 基址）修复后再进 rizin。
  4. 校验：`rz-bin -I` / `file` 确认 ELF class/arch 正常后再继续。
  5. dump 前判断是否 self-hook（见特征 3）。

## 特征 2：杀进程不走符号（内联 shellcode exit_group）

- **是什么**：杀进程不调 `kill/tgkill/exit/syscall` 这些有名符号，而是用**运行时解密出的内联 shellcode**，`mmap RWX` 后直接执行 `exit_group(0)`，完全不经过 libc 符号。
- **怎么识别**：符号级 hook 挂 `kill/tgkill/exit` 扑空；`syscall-filter` 抓到 `exit_group` 但 pc 落在匿名 RX/RWX（无文件映射）；反编译里出现「运行时拼密文 + 密钥解密 + mmap RWX + 直接执行」的片段；`JNI_OnLoad` 日志标签常含加固商名（如 `NagaLinker`）。
- **应对**：
  1. 不能以「符号级 hook 扑空」推论「无杀进程」。用 syscall-filter + `--raw`/syscall dump 拿回原始镜像再解剖。
  2. 定位**运行时解密出的 exit_group 执行器**（可能多个，如 4 个执行器）→ patch 落在 dump/fix 后的执行器上，`replace 成 no-op`。
  3. 若执行器在匿名 RX/RWX，先 dump/fix 该匿名段，再以其产物为准分析、patch、验证。

## 特征 3：self-hook 底层函数（open/write）防 dump/hook

- **是什么**：壳自己 hook 了 libc 的 `open`/`write` 等底层函数，你一调用它们（如写文件 dump）就被它检测到并杀进程。
- **怎么识别**：正常 Frida dump/写文件就被 kill；日志显示「hook 到之后、没 dump 就被 kill」；怀疑壳改写了底层 IO 函数。
- **应对**：改用 **syscall 直接 dump**（`syscall(SYS_openat)`/`syscall(SYS_write)`），绕过被 hook 的 libc 层；部分无权限内存空间也要 dump 防遗漏。

## 特征 4：运行时 dlopen + dlsym 自解析符号（避开导入表）

- **是什么**：要用的函数（如 `pthread_create`）**不写进导入表**，而是运行时 `dlopen("libc.so")` + `dlsym` 动态拿函数指针再调用。
- **怎么识别**：导入表/字符串表里找不到该函数；运行时在栈上拼字符串、用某密钥解密出 "libc.so" 和函数名；出现 `dlopen`+`dlsym` 调用。
- **应对**：看导入表会漏。要跟踪运行时自解析：hook `dlopen`/`dlsym` 或看运行时解密出的字符串；定位调用点后在**动态解析后的函数调用处**或**运行时解密逻辑**上做 patch。

## 特征 5：自写 ELF 解析器 + 自建符号注册表（连 dlopen/dlsym 都不用）

- **是什么**：壳自己实现一套「解析 ELF 找符号」的逻辑（解析 PHDR/SHDR/.got/.dynstr/.rel.*、DT_ANDROID_*）+ 自建符号注册表，连 dlopen/dlsym 都不用，JNI_OnLoad 通过自建表转发真正的 JNI_OnLoad。
- **怎么识别**：导入表没有 dlopen/dlsym，却能拿函数；反编译里出现自实现 ELF 解析器（解析 section/dynamic/reloc 的代码）和自建符号表（构建函数 + 查询函数）；存在 `register+...` / `query+...` 的一对符号表函数。
- **应对**：这是比 dlopen/dlsym 更彻底的隐藏。逆向更依赖**运行时行为**（syscall-filter、Stalker trace、watch 关键 API 结果），而不是静态导入表。定位其自建符号表查询函数，看它把哪些函数地址交给谁，再决定 patch 点。

## 特征 6：多入口 + 多线程看门狗分散触发

- **是什么**：检测不只在单一入口，而是在 `.init`、`.init_array`、`JNI_OnLoad` 多处 + 多个后台看门狗线程分散触发。
- **怎么识别**：解析 ELF 动态段（DT_INIT / DT_INIT_ARRAY / DT_FINI_ARRAY）拿到入口清单；从入口/dispatcher 找 `pthread_create` 或运行时解密出的线程入口；多个线程入口分别做不同检测。
- **应对**：必须枚举全部入口 + 全部看门狗线程，逐个确认检测对象/触发条件/杀进程出口；不能以「已过某入口」作为通过结论。

## 特征 7：inline hook 检测（trampoline 特征匹配）

- **是什么**：检测函数**开头是否被改成跳转指令**（trampoline，如 `LDR+BR`、`B` 跳转），匹配到就判定「被 hook」。
- **怎么识别**：反编译里出现「读目标函数开头字节 → 与 trampoline 模式比对 → 判定」的逻辑；检测函数常叫 `isHooked`/`sub_43..` 之类；用 `process_vm_readv` 跨进程读内存检测。
- **应对（打蛇打七寸）**：找到被多处复用的**核心检测原语**，让它**恒返回「未检测到 hook」**，则所有调用者走「环境干净」分支、不读 buffer → 一次绕过所有依赖它的 hook 检测。若还检 Java 层，单独把 `isHooked` 类的 ArtMethod 入口检查也恒返回干净值。

## 特征 8：Frida 痕迹检测（线程名 / fd / maps 指纹）

- **是什么**：扫描 `/proc/self/task`（线程名）、`/proc/self/fd`（打开的 fd）、`/proc/self/maps`（内存映射），识别 Frida 特征。
- **怎么识别**：字符串/反编译里出现 `gum-js-loop`、`gmain`（Frida 线程名）、`linjector`（注入器）、`frida-agent`、`_AGENT_1.0`、`/data/local/tmp`、`/proc/self/...` 路径。
- **应对**：命中线程名扫描 → 把对应扫描函数恒返回「空/0」；隐藏 Frida 特征（改 agent 名/线程名/端口，或用改版 frida/gadget 降特征）。

## 特征 9：环境异常检测（TracerPid / PPid / T 态 / ADB / root / 模拟器 / xposed）

- **是什么**：检测是否被 ptrace 跟踪（TracerPid）、父进程 PPid、线程 T 态、ADB/USB 调试、root、模拟器、xposed 等。
- **怎么识别**：反编译里出现读 `/proc/self/status` 的 `TracerPid`、`PPid`；查 `sys.usb.config` 含 `adb`；查 root/xposed/模拟器特征。
- **应对**：把对应检测函数恒返回「正常值」（0/1/NULL）；或用隐藏手段（改 TracerPid 返回值、隐藏 root/xposed 特征）。P2 级最低危的可暂缓处理。

## 特征 10：检测位图（bitmap 状态汇总）

- **是什么**：壳用一个位图记录「检测到哪些异常」，每 bit 对应一种检测（root/frida/hook/emulator/xposed/...），一旦置位就上报/杀进程。
- **怎么识别**：反编译里出现一个全局位图/状态变量，多处检测往不同 bit 置位，入口处汇总判断。
- **应对**：找到**汇总判断位图**的位置，让「环境异常」分支不执行、或把状态位清零/恒判干净。

## 特征 11：CRC / 完整性校验（自身 .text / libc / libart）

- **是什么**：对自身 `.text`、`libc.so`、`libart.so`（有时含 linker、dex、APK 签名）做 CRC/hash/逐字节比对，失配则自毁。
- **怎么识别**：读 `/proc/self/maps` 定位 r-x 段；`openat` 目标 so + `read/mmap` 与内存逐字节比对；`memcmp`/CRC/adler/hash 循环（文件 vs 内存、内存 vs 常量）；失配跳 `__stack_chk_fail`、清栈跳非法地址、自发 SIGSEGV；字符串含自身 so 名、`libc.so`、`/proc/self/maps`。
- **应对**：干掉检测代码本身（定位 CRC 校验函数与中央 kill 出口）；让校验函数恒返回「未篡改」或让执法分支不执行；或改用不改被校验 `.text` 的手段（HWBP replace-ret、改全局状态变量、双映射/影子页）。分析算法类任务无 frida 检测用 frida、有则用 HWBP。详细见 `workflow-standards.md` §9。

## 特征 12：dump——复用壳自己的 API / 结构

- **是什么**：作者借壳已准备好的对象（如壳自己拿到的 `pthread_create`）一次性做 patch，省去自建。
- **怎么识别**：壳为某个目的已 `dlopen`+`dlsym` 拿到某函数/句柄，或已建好某注册表。
- **应对**：**复用壳已准备的工具/注册表**做 patch，避免重复造轮子；一次 hook 里批量处理多个 P0/P1 点。

## 特征 13：trace/hook 打印开销导致 agent 卡死

- **是什么**：Frida 脚本里打印调用栈/trace 过多，执行慢到把 agent 卡死；特定函数被反复调用时尤为严重。
- **怎么识别**：脚本能跑但极慢/超时/无响应；删掉打印后变快。
- **应对**：只保留「动手 patch 的核心动作」，**删掉/关闭调用栈打印和过重 trace**；Stalker trace 目标化分段下钻，不从头无脑踩。

---

## 速查表（特征 → 首处应对）

| 命中特征 | 首处应对 | 详见 |
|---|---|---|
| SMC/自解密 | dump/fix + SoFixer | 特征 1 |
| 杀进程不走符号 | syscall-filter + dump 解剖内联 shellcode | 特征 2 |
| self-hook open/write | syscall dump | 特征 3 |
| dlopen+dlsym 自解析 | 跟踪运行时自解析 | 特征 4 |
| 自写 ELF 解析器+自建符号表 | 靠运行时行为定位 | 特征 5 |
| 多入口多线程 | 枚举全部入口+看门狗线程 | 特征 6 |
| inline hook 检测 | 核心原语恒返回干净 | 特征 7 |
| Frida 痕迹 | 对应扫描函数恒返回空/隐藏特征 | 特征 8 |
| TracerPid/ADB/root/模拟器 | 对应检测函数恒返回正常 | 特征 9 |
| 检测位图 | 让位图汇总判环境干净 | 特征 10 |
| CRC/完整性 | 干掉 CRC 校验/执法分支 | 特征 11 |
| 复用壳自身 API | 借壳已备好的对象做 patch | 特征 12 |
| trace 打印卡死 | 删打印/关重 trace | 特征 13 |

---

## 边界与注意事项

- 每版壳特征随版本/加固商变化，**上述特征与应对以目标样本实际证据为准**；地址、函数名、偏移需反编译后确认，不能照搬本文数值。
- 特征可叠加；命中多条时逐个匹配、逐个过，不因已过一条就收工。
- 「应对」多数是让检测函数恒返回「干净值」/「end 分支不执行」，属于 patch 目标；patch 前仍须走 `workflow-standards.md` §10 的归属边界与崩溃原因门禁。
- 涉及 Frida 使用前按 `workflow-standards.md` §11 确认 frida-server 状态与版本匹配；不自行更换版本。
- 杀进程/自毁相关：先 syscall-filter 定位 syscall 与 pc/lr/sp 归属，再 dump/fix + 静态分析，未完成前禁止纯动态试错。
