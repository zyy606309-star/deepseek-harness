# 壳特征库（壳厂商画像 + 手法索引）

> 本文分两层，便于快速定位：
> - **第一层「壳厂商画像」**：按加固厂商组织，一眼看该壳的完整手法组合 + 整体应对思路。
> - **第二层「手法索引」**：按"壳干了什么"跨壳组织，遇到未知壳/单点手法时按特征快速匹配。
>
> 使用方式：**先认壳 → 看厂商画像**；**认不出壳或只想查某个手法 → 查手法索引**。特征可叠加，命中多条逐个过，不因已过一条就收工。具体地址/函数名/偏移以目标样本实际证据为准。
>
> **防守方对照**：每个手法的"风控侧定义/判据/处置"见 `references/risk-control-map.md`（数据已入库 `references/risk-control-data/`）。攻击（壳特征）↔ 防守（风控规则）互相印证，能更精确知道"要骗过风控的哪些条件"。

---

## 第一层：壳厂商画像

### 梆梆（Bangcle / 爱加密系，标志：`libDexHelper.so` + `assets/classes.dve` + `meta-data/rsa.sig`）

- **代表性文章**：看雪 292547（frida 检测绕过）、292801（梆梆逆向实战）
- **手法组合**：
  - 特征 1 SMC / 自解密（so 磁盘乱码）
  - 特征 16 低地址自毁签名（清 SP/LR + BR 低地址）
  - 特征 17 反静态门槛（.text 垃圾字节 + 检测串 XOR）
  - 特征 18 自毁升级（多终止原语变种）
  - 特征 19 页0 retstub 环境依赖
  - 特征 20 多进程看门狗守护
  - 特征 21 syscall 走指针表
  - 特征 22 dex 藏 native heap + 选择性加固
  - 特征 7 inline hook 检测、特征 8 Frida 痕迹、特征 9 环境异常、特征 11 CRC/完整性
- **整体应对**：先认「自毁签名」（低地址+sp/lr清零+回溯打空）→ 摸检测面（过反静态门槛）→ 源头 NOP 自毁点 + 按终止原语类兜底 + 页0 retstub + seccomp → 先冻看门狗再冻 main → 压住自毁让 App 跑起来 → 从 native heap（scudo:secondary）按 dex endian_tag 锚点脱业务 dex。

### 娜迦（Naga，标志：`libmsaoaidsec.so`，JNI_OnLoad 日志标签 `NagaLinker v8.83`）

- **代表性文章**：看雪 292547（娜迦杀进程）、291403（娜迦 Hook 时机）
- **手法组合**：
  - 特征 2 杀进程不走符号（内联 shellcode exit_group）
  - 特征 4 dlopen+dlsym 自解析（拿 pthread_create）
  - 特征 5 自写 ELF 解析器 + 自建符号注册表
  - 特征 6 多入口 + 多线程看门狗
  - 特征 14 检测在早期初始化（.init/.init_proc/.init_array）
  - 特征 15 早期环境探测（__system_property_get）
  - 特征 9 环境异常（TracerPid/ADB/root）、特征 8 Frida 痕迹、特征 11 CRC
- **整体应对**：先解决 Hook 时机（onEnter + 二级锚点，别用 onLeave）→ 枚举全部入口+看门狗线程 → 分级 patch（P0 杀点 no-op / P1 检测恒返回正常 / P2 暂缓）→ 注意杀进程走内联 shellcode、符号级 hook 会扑空。

### 爱加密（ijiami，标志：`libexec.so` + `assets/ijiami.dat` / `ijiami.ajm`）

- **代表性文章**：看雪 292771（某加密企业版 Frida 检测绕过）
- **手法组合**：
  - 特征 1 SMC / 自解密（libexec.so 大段加密，疑似轻改 UPX）
  - 特征 8 特征：VM 调度器 / A-table 检测（gate 链 ops 表 + A[7]/A[4]/A[31]）
  - 特征 特征：TracerPid / wchan / ptrace_stop 检测
  - 特征 新：**方法级抽取 DEX**（`ijiami.dat` 恢复方法抽空的 DEX 骨架，`ijiami.ajm` 存 142k 条方法体按 marker 回填）
  - 特征 6 多入口多线程、特征 11 CRC/完整性、特征 14 早期检测
- **整体应对**：先 hook dlopen 定位处决逻辑所在 so（用 sleep 应对检测滞后）→ dump + SoFixer 修复 libexec.so → trace 定位检测点（AI 写 + sleep + 二分）→ 打蛇打七寸（精确 caller 条件改返回 + 持续清检测状态位 + 多窗口安装）→ 脱 DEX 时注意**方法级抽取**：结构校验通过≠方法恢复，要扫 NOP/默认返回骨架、debug_info_off 异常 marker。

> 其它厂商（腾讯乐固、360 加固等）遇到后再补充；上述画像以已学文章为依据，实际样本以证据为准。

---

## 第二层：手法索引（跨壳复用）

### 特征 1：SMC / 自解密 so（磁盘乱码，运行时才解密）

- **是什么**：so 在磁盘上是加密乱码，运行时才在内存里解密/重建为可执行代码。
- **怎么识别**：直接反编译磁盘 so 出不来有效代码；`rz-bin -I`/`file` 显示 bintype/class 正常但段表/程序头/字符串表异常；rizin 只识别导入桩或少量函数、无有效 `.text`；运行 pc/lr 不落在磁盘可解释代码；constructor/JNI_OnLoad 申请匿名 RX 并解密。
- **应对（dump/fix 硬门禁）**：
  1. 必须**运行时 dump** 真实镜像 + 修复，禁止直接分析磁盘 so 下结论 / 给 patch。
  2. dump 时机权衡：越晚越完整（解密全）、越晚越危险（开始检测+杀）。constructor 短窗口/快速闪退用 `frida_memdump_so.py`，稳定进程用 `memdump_so.py`。
  3. `--raw`/syscall/手工 dump 拿回的是畸形 ELF → 宿主机 **SoFixer**（`sofixer_run.py`，`-m` 必须 = dump 基址）修复后再进 rizin。
  4. 校验：`rz-bin -I` / `file` 确认 ELF class/arch 正常后再继续。
  5. dump 前判断是否 self-hook（见特征 3）。
- **用过该手法的壳**：梆梆、娜迦、多数加密壳。

### 特征 2：杀进程不走符号（内联 shellcode exit_group）

- **是什么**：杀进程不调 `kill/tgkill/exit/syscall` 这些有名符号，而是用**运行时解密出的内联 shellcode**，`mmap RWX` 后直接执行 `exit_group(0)`，完全不经过 libc 符号。
- **怎么识别**：符号级 hook 挂 `kill/tgkill/exit` 扑空；`syscall-filter` 抓到 `exit_group` 但 pc 落在匿名 RX/RWX（无文件映射）；反编译里出现「运行时拼密文 + 密钥解密 + mmap RWX + 直接执行」的片段；`JNI_OnLoad` 日志标签常含加固商名（如 `NagaLinker`）。
- **应对**：
  1. 不能以「符号级 hook 扑空」推论「无杀进程」。用 syscall-filter + `--raw`/syscall dump 拿回原始镜像再解剖。
  2. 定位**运行时解密出的 exit_group 执行器**（可能多个，如 4 个执行器）→ patch 落在 dump/fix 后的执行器上，`replace 成 no-op`。
  3. 若执行器在匿名 RX/RWX，先 dump/fix 该匿名段，再以其产物为准分析、patch、验证。
- **用过该手法的壳**：娜迦。

### 特征 3：self-hook 底层函数（open/write）防 dump/hook

- **是什么**：壳自己 hook 了 libc 的 `open`/`write` 等底层函数，你一调用它们（如写文件 dump）就被它检测到并杀进程。
- **怎么识别**：正常 Frida dump/写文件就被 kill；日志显示「hook 到之后、没 dump 就被 kill」；怀疑壳改写了底层 IO 函数。
- **应对**：改用 **syscall 直接 dump**（`syscall(SYS_openat)`/`syscall(SYS_write)`），绕过被 hook 的 libc 层；部分无权限内存空间也要 dump 防遗漏。
- **用过该手法的壳**：梆梆（292801）、娜迦（292547）。

### 特征 4：运行时 dlopen + dlsym 自解析符号（避开导入表）

- **是什么**：要用的函数（如 `pthread_create`）**不写进导入表**，而是运行时 `dlopen("libc.so")` + `dlsym` 动态拿函数指针再调用。
- **怎么识别**：导入表/字符串表里找不到该函数；运行时在栈上拼字符串、用某密钥解密出 "libc.so" 和函数名；出现 `dlopen`+`dlsym` 调用。
- **应对**：看导入表会漏。要跟踪运行时自解析：hook `dlopen`/`dlsym` 或看运行时解密出的字符串；定位调用点后在**动态解析后的函数调用处**或**运行时解密逻辑**上做 patch。
- **用过该手法的壳**：娜迦（pthread_create）、梆梆（OpenMemory）。

### 特征 5：自写 ELF 解析器 + 自建符号注册表（连 dlopen/dlsym 都不用）

- **是什么**：壳自己实现一套「解析 ELF 找符号」的逻辑（解析 PHDR/SHDR/.got/.dynstr/.rel.*、DT_ANDROID_*）+ 自建符号注册表，连 dlopen/dlsym 都不用，JNI_OnLoad 通过自建表转发真正的 JNI_OnLoad。
- **怎么识别**：导入表没有 dlopen/dlsym，却能拿函数；反编译里出现自实现 ELF 解析器（解析 section/dynamic/reloc 的代码）和自建符号表（构建函数 + 查询函数）；存在 `register+...` / `query+...` 的一对符号表函数。
- **应对**：这是比 dlopen/dlsym 更彻底的隐藏。逆向更依赖**运行时行为**（syscall-filter、Stalker trace、watch 关键 API 结果），而不是静态导入表。定位其自建符号表查询函数，看它把哪些函数地址交给谁，再决定 patch 点。
- **用过该手法的壳**：娜迦。

### 特征 6：多入口 + 多线程看门狗分散触发

- **是什么**：检测不只在单一入口，而是在 `.init`、`.init_array`、`JNI_OnLoad` 多处 + 多个后台看门狗线程分散触发。
- **怎么识别**：解析 ELF 动态段（DT_INIT / DT_INIT_ARRAY / DT_FINI_ARRAY）拿到入口清单；从入口/dispatcher 找 `pthread_create` 或运行时解密出的线程入口；多个线程入口分别做不同检测。
- **应对**：必须枚举全部入口 + 全部看门狗线程，逐个确认检测对象/触发条件/杀进程出口；不能以「已过某入口」作为通过结论。
- **用过该手法的壳**：娜迦、梆梆。

### 特征 7：inline hook 检测（trampoline 特征匹配）

- **是什么**：检测函数**开头是否被改成跳转指令**（trampoline，如 `LDR+BR`、`B` 跳转），匹配到就判定「被 hook」。
- **怎么识别**：反编译里出现「读目标函数开头字节 → 与 trampoline 模式比对 → 判定」的逻辑；检测函数常叫 `isHooked`/`sub_43..` 之类；用 `process_vm_readv` 跨进程读内存检测。
- **应对（打蛇打七寸）**：找到被多处复用的**核心检测原语**，让它**恒返回「未检测到 hook」**，则所有调用者走「环境干净」分支、不读 buffer → 一次绕过所有依赖它的 hook 检测。若还检 Java 层，单独把 `isHooked` 类的 ArtMethod 入口检查也恒返回干净值。
- **用过该手法的壳**：梆梆（libDexHelper）、多数反 hook 壳。

### 特征 8：Frida 痕迹检测（线程名 / fd / maps 指纹）

- **是什么**：扫描 `/proc/self/task`（线程名）、`/proc/self/fd`（打开的 fd）、`/proc/self/maps`（内存映射），识别 Frida 特征。
- **怎么识别**：字符串/反编译里出现 `gum-js-loop`、`gmain`（Frida 线程名）、`linjector`（注入器）、`frida-agent`、`_AGENT_1.0`、`/data/local/tmp`、`/proc/self/...` 路径。
- **应对**：命中线程名扫描 → 把对应扫描函数恒返回「空/0」；隐藏 Frida 特征（改 agent 名/线程名/端口，或用改版 frida/gadget 降特征）。
- **用过该手法的壳**：娜迦、梆梆。

### 特征 9：环境异常检测（TracerPid / PPid / T 态 / ADB / root / 模拟器 / xposed）

- **是什么**：检测是否被 ptrace 跟踪（TracerPid）、父进程 PPid、线程 T 态、ADB/USB 调试、root、模拟器、xposed 等。
- **怎么识别**：反编译里出现读 `/proc/self/status` 的 `TracerPid`、`PPid`；查 `sys.usb.config` 含 `adb`；查 root/xposed/模拟器特征。
- **应对**：把对应检测函数恒返回「正常值」（0/1/NULL）；或用隐藏手段（改 TracerPid 返回值、隐藏 root/xposed 特征）。P2 级最低危的可暂缓处理。
- **用过该手法的壳**：娜迦、梆梆、绝大多数反调试壳。

### 特征 10：检测位图（bitmap 状态汇总）

- **是什么**：壳用一个位图记录「检测到哪些异常」，每 bit 对应一种检测（root/frida/hook/emulator/xposed/...），一旦置位就上报/杀进程。
- **怎么识别**：反编译里出现一个全局位图/状态变量，多处检测往不同 bit 置位，入口处汇总判断。
- **应对**：找到**汇总判断位图**的位置，让「环境异常」分支不执行、或把状态位清零/恒判干净。
- **用过该手法的壳**：梆梆（libDexHelper）。

### 特征 11：CRC / 完整性校验（自身 .text / libc / libart）

- **是什么**：对自身 `.text`、`libc.so`、`libart.so`（有时含 linker、dex、APK 签名）做 CRC/hash/逐字节比对，失配则自毁。
- **怎么识别**：读 `/proc/self/maps` 定位 r-x 段；`openat` 目标 so + `read/mmap` 与内存逐字节比对；`memcmp`/CRC/adler/hash 循环（文件 vs 内存、内存 vs 常量）；失配跳 `__stack_chk_fail`、清栈跳非法地址、自发 SIGSEGV；字符串含自身 so 名、`libc.so`、`/proc/self/maps`。
- **应对**：干掉检测代码本身（定位 CRC 校验函数与中央 kill 出口）；让校验函数恒返回「未篡改」或让执法分支不执行；或改用不改被校验 `.text` 的手段（HWBP replace-ret、改全局状态变量、双映射/影子页）。分析算法类任务无 frida 检测用 frida、有则用 HWBP。详细见 `workflow-standards.md` §9。
- **用过该手法的壳**：梆梆、娜迦、多数加固壳。

### 特征 12：dump——复用壳自己的 API / 结构

- **是什么**：作者借壳已准备好的对象（如壳自己拿到的 `pthread_create`）一次性做 patch，省去自建。
- **怎么识别**：壳为某个目的已 `dlopen`+`dlsym` 拿到某函数/句柄，或已建好某注册表。
- **应对**：**复用壳已准备的工具/注册表**做 patch，避免重复造轮子；一次 hook 里批量处理多个 P0/P1 点。
- **用过该手法的壳**：娜迦（复用 pthread_create patch P0）。

### 特征 13：trace/hook 打印开销导致 agent 卡死

- **是什么**：Frida 脚本里打印调用栈/trace 过多，执行慢到把 agent 卡死；特定函数被反复调用时尤为严重。
- **怎么识别**：脚本能跑但极慢/超时/无响应；删掉打印后变快。
- **应对**：只保留「动手 patch 的核心动作」，**删掉/关闭调用栈打印和过重 trace**；Stalker trace 目标化分段下钻，不从头无脑踩。
- **用过该手法的壳**：不特定（通用工程经验）。

### 特征 14：检测逻辑在早期初始化（.init / .init_proc / .init_array），不等到 JNI_OnLoad

- **是什么**：加固 so 把反调试/反 Hook/完整性校验放在 `.init`、`.init_proc` 或 `.init_array`（so 加载最早期的初始化阶段），**提前到 JNI_OnLoad 之前**执行。
- **怎么识别**：解析 ELF 动态段（DT_INIT → `.init_proc`、DT_INIT_ARRAY → 构造数组）发现早期初始化入口；`android_dlopen_ext` 的 **onLeave 时检测已跑完**（App 闪退/退出/流程异常，即使没到 JNI_OnLoad）；早期初始化里出现 `__system_property_get`、读 maps、扫线程等环境探测调用。
- **应对（Hook 时机要早于检测阶段）**：
  1. 检测有早期初始化特征时，`android_dlopen_ext`/`dlopen` 的 **onLeave 太晚**（onLeave 触发时 .init/.init_array 已执行完）。改用 **onEnter**（so 刚进入加载流程、初始化还没跑）。
  2. 先判断检测逻辑到底在 `.init`/`.init_array`/JNI_OnLoad 哪个阶段，再选 Hook 时机，不默认"过了 onLeave 再 hook"。
  3. **用"外部导入函数"当二级锚点**：找早期初始化函数（如 `.init_proc`）内部调用的**外部导入函数**（如 `__system_property_get`），在它被调用时确认"初始化已跑起来 + 目标 so 基址已知"，此时装 Hook 时机最合适；比盲目轮询模块加载更稳定，可用属性名/路径过滤避免误伤其它模块。
- **用过该手法的壳**：娜迦（libmsaoaidsec）。

### 特征 15：早期环境探测 = 检测起点（__system_property_get 读 SDK/属性）

- **是什么**：`.init_proc` 等早期初始化就调用 `__system_property_get`（如读 `ro.build.version.sdk`）、读 maps、扫线程做环境探测，并据此决定启用哪些检测。
- **怎么识别**：`.init_proc` / 早期子函数里出现 `__system_property_get`、字符串表里有 `ro.build.version.sdk` 等属性名；导入表里有 `__system_property_get`。
- **应对**：把 `__system_property_get` 当**最早、最值得 hook 的锚点**；通过过滤属性名（只在目标 so 读取时才装 Hook）精确定位，可在检测逻辑真正执行前建立观测/装 Hook。静态分析时优先确认 init 早期调用链。
- **用过该手法的壳**：娜迦。

### 特征 16：低地址自毁签名（清 SP/LR + BR 低地址）

- **是什么**：壳检测到异常后，**主动清 SP、清 LR、BR 到非法低地址**（<0x1000，如 0x1f4/0x61c/0x79c），制造"既崩、又让工具回溯不出栈"的崩溃。
- **怎么识别**（认签名别认字面）：崩溃日志 pc 落在**非法低地址** + sp=0 + lr=0 + backtrace 只有空帧 = 壳主动自毁（普通野指针 pc 在真实 so、sp/lr 有效、能回溯）。字节指纹（ARM64）：`MOV X0,#0(0xD2800000)` + `MOV SP,X0(0x9100001F)` + `MOV X30,X0(0xAA0003FE)` + `BR Xn`。
- **应对**：源头 NOP 自毁点（改成 `NOP;NOP;NOP;RET`）；按终止原语类兜底（见特征 18）；页0 retstub 兜漏网动态自毁点（见特征 19）。
- **⚠️ 陷阱**：自毁编码**随 build 变**（清 SP/LR 有 `mov sp,xzr(0x910003ff)` 和 `mov sp,x0(0x9100001f)` 两种写法，字节完全不同）；魔数（如 `0xB6A2`）是通用哨兵、普通代码也用（60+ 处），**不能单独当判据**。必须**锚整段序列、不照抄偏移/魔数**，对手上这份 so 重新逆。
- **用过该手法的壳**：梆梆。

### 特征 17：反静态门槛（.text 垃圾字节 + 检测串 XOR 加密）

- **是什么**：① `.text` 代码段撒**垃圾字节**（非法指令），让线性反汇编撞到就停、扫不全；② 检测串（MAGISK/ptrace/crc32 等）用 **XOR(key=0xAC) 加密**，`strings` 只见诱饵、代码零直接引用。
- **怎么识别**：capstone 一次 pass 只覆盖第一段、直接扫引用点得 0 个（改容错扫描后变多）；`strings | grep -i magisk` 出来的是明文但代码对它们零 adrp+add 引用，真正用加密 blob。
- **应对**：① 反汇编用"每 4 字节 try、失败跳过"的**容错扫描**；② 找**解密循环 + 加密 blob** 组合（例：XOR key=0xAC，一次解 16 字节），而不是认明文关键词。
- **用过该手法的壳**：梆梆。

### 特征 18：自毁升级（多终止原语变种）

- **是什么**：把自毁点 NOP 掉后，壳换一种自毁方式，每压一层升一级：① 清 SP/LR + BR 对齐低地址 → SIGSEGV；② BR 非对齐低地址 0x1（毒 lr=1）→ SIGBUS；③ `__stack_chk_fail → abort` → SIGABRT；④ kill 家族 → SIGKILL。
- **怎么识别**：压制一种自毁后换另一种信号/崩溃方式出现；崩溃类型从 SIGSEGV → SIGBUS → SIGABRT/SIGKILL 变化。
- **应对**：**按终止原语类兜底，不逐点堵**——"让进程终止"的手段只有硬件 fault(SIGSEGV/SIGBUS) / abort(SIGABRT) / kill(SIGKILL) / exit 这几类，按类兜底才收敛（见 workflow-standards.md §10 自毁压制兜底策略）。
- **用过该手法的壳**：梆梆。

### 特征 19：页0 retstub（兜漏网低地址自毁）+ 环境依赖

- **是什么**：把内存第 0 页（0x0~0xFFF）映射成可执行、填满 `RET`，让漏网"跳低地址"的自毁执行到 RET 无害。
- **怎么识别**：自毁点跳到低地址，且动态自毁点扫不到（在匿名内存里运行时生成）。
- **应对**：页0 retstub + 短周期线程持续重填 RET（壳会写脏）。⚠️ **环境依赖**：严格 SELinux 真机要 `echo 0 > /proc/sys/vm/mmap_min_addr` + `setenforce 0`，否则 `mmap page 0` 失败（`Operation not permitted`）；云机/redroid 容器通常宽松。跨设备移植要单独确认这一层。
- **用过该手法的壳**：梆梆。

### 特征 20：多进程看门狗守护（main fork 子进程反制）

- **是什么**：main 进程 fork 出看门狗子进程盯着它，main 一被冻/被改，看门狗就 SIGKILL 它。
- **怎么识别**：
  - 直接 `kill -STOP` 冻 main，几百 ms 内被 SIGKILL；`ps` 看到同名多进程（main + 看门狗子进程，子进程 PPID = main PID、线程数少）。
  - **hook `clone`/`fork` 观察子进程**（更早、更稳，不依赖 kill -STOP 试错）：在 `clone` 返回处看是否 fork 出独立检测子进程，记录子进程 PID、入口、以及它`重新解密/加载了什么`。
- **⚠️ 误判警告：fork 不是补丁继承**：子进程**不**是 COW 继承父进程的 patch，而常常是**重新解密了内层 ELF、基址不同**——父进程内的 patch 根本覆盖不到子进程所在的检测载体。所以「patch 主进程」不等于「过了检测」，必须**先确认检测逻辑到底在哪个进程**，再决定 patch 落点；只在主进程内 patch，子进程的检测照样触发 SIGKILL。
- **应对**：**有序 SIGSTOP**——先冻看门狗子进程、再冻 main（此时 main 冻住也无法再 fork 新看门狗）。这是对付多进程自守的通用手法。**击杀/冻结检测载体进程 = 让检测函数不再执行，不等于环境层隐藏 root**（属于函数级/进程级绕过，不违背授权边界）。
- **用过该手法的壳**：梆梆。

### 特征 21：syscall 走指针表（不 via libc PLT）

- **是什么**：关键 syscall（ptrace 等）**不 `bl` libc 的 PLT**，而是运行时用 libc 基址填一张**自建指针表**，调用时 `ldr xN,[表+偏移]` + `blr xN` 间接调。调用点看不到符号名。
- **怎么识别**：hook libc 关键导出（如 ptrace）后从启动到崩溃**全程零命中**；反汇编里调用点是"从自建表取地址再跳"而非 `bl <符号@PLT>`；导入表没有对应符号或直接 syscall（svc 0）。
- **应对**：符号级 hook 失效，要在**更底层**动手——seccomp 拦 syscall 入口，或 hook 指针表填充点（运行时填地址处），而不是挂 libc 符号。
- **用过该手法的壳**：梆梆。

### 特征 22：dex 藏 native heap（不落 dalvik-DEX data 区）+ 选择性加固

- **是什么**：① 解密出的明文 dex 用 `dlsym(art::DexFile::OpenMemory)` **就地引用 native heap**（`[anon:scudo:secondary]`），ART 不 copy 到 `[anon:dalvik-DEX data]` 区；② **选择性加固**——只加密 App 自研业务类，框架/三方库保持明文。
- **怎么识别**：常规脱壳工具扫不到 dex（main 进程无 `[anon:dalvik-DEX data]` 区）；`classes.dex` 里只有框架类（androidx/com.google 等）、业务类（如 com/byb）一个都没有；maps 里 `[anon:scudo:secondary]` 有几十 MB 大块，strings 能扫到业务类描述符。
- **应对**：① 先压住自毁、App 跑起来让 dex 解密；② 读 maps 排除 GC region-space，盯 scudo:secondary，用业务类描述符核对；③ `dd if=/proc/<pid>/mem` 按页拉出；④ 按 dex 头锚点 `endian_tag=0x12345678`（字节 `78 56 34 12` @ 0x28）逐个 dump，补回被抹的 8 字节魔数 `dex\n035\0`。⑤ 框架层 hook 点不用脱壳（明文），只有动业务逻辑才非脱不可。
- **用过该手法的壳**：梆梆。

### 特征 23：方法级抽取 DEX（骨架在，方法体抽空）

- **是什么**：DEX **结构合法**（能过 dexdump 结构校验），但**方法体被抽空**——被替换成"默认返回 / NOP 骨架"；真正的方法体加密存放在另一个文件里（如 `ijiami.dat` 恢复骨架、`ijiami.ajm` 存 14 万+ 条方法体按 marker 回填）。
- **怎么识别**：`assets/ijiami.dat`、`assets/ijiami.ajm` 这类**磁盘占用大、信息熵高**的文件很可能是加密 DEX / 方法体；解出的 DEX 能过结构校验但**业务方法大量是默认返回/NOP**；`debug_info_off` 异常 marker；业务类保留 try 块但**首条即 return**。
- **应对**：① 沿字符串 + xref 静态追踪定位解密逻辑（密钥常量可暴力穷举 + 文件魔数约束）；② 用 `ijiami.ajm` 的方法体记录**按 marker 原位回填**到 DEX 骨架；③ **判断"真恢复"不能只看结构校验**，必须额外扫 NOP/默认返回骨架、`debug_info_off` 异常 marker、业务类 try 块首条 return。大模型常停在"能打开 DEX"就不动，需主动提醒。
- **用过该手法的壳**：爱加密（ijiami）。

### 特征 24：VM 调度器 / A-table 检测（gate 链 ops 表 + A[N] 表）

- **是什么**：核心检测逻辑用 **VM（虚拟机）调度器**执行——如构造期 VM 调度器（`sub_5CCF8`）跑 VM 字节码，再用"VM 结果栈提取器"（`sub_DDF94`）取结果，返回 1 = 检测命中；检测表用 **A-table**（如 A[7]/A[4]/A[31] 分别对应不同检测，A-table 用下标取函数）。
- **怎么识别**：反编译里出现"调某函数去跑 VM 字节码 + 另取结果"的调度结构；或"用固定表下标（A[7] 等）取检测函数"；gate 链里有 `ops[0x00]` 这类 thunk。
- **应对**：找出 VM 调度器 + 结果提取器，分别 hook（命中改 0）；注意结果提取器可能**被多处复用**（如还被 `JNI_OnLoad` 用来返回 `JNI_VERSION`），只能**按 caller 区间精确改**。A-table 里的具体检测（读 `/proc/self/status` 解析 TracerPid、读 `/proc/self/wchan` 识别 `sys_epoll`/`ptrace_stop`、字符串比较 helper）分别 hook 改 0。
- **用过该手法的壳**：爱加密（ijiami，企业版 VMP）。

### 特征 25：TracerPid / wchan / ptrace_stop 检测

- **是什么**：通过读 `/proc/self/status` 解析 **TracerPid**（是否被 ptrace 跟踪）、读 `/proc/self/wchan` 识别 `sys_epoll`/`ptrace_stop`（是否被挂起/跟踪）、以及配套的字符串比较 helper，来判断是否被调试/挂起。
- **怎么识别**：反编译里出现直接 syscall 打开/读 `/proc/self/status` 解析 TracerPid 的逻辑；读 `/proc/self/wchan` 匹配 `sys_epoll`/`ptrace_stop`；字符串比较 helper 匹配这些行名。
- **应对**：对应检测函数（如 A[7] TracerPid 解析、A[4] wchan、A[31] 字符串比较 helper）逐个 hook 改 0。
- **用过该手法的壳**：爱加密（ijiami）。

---

## 速查表（特征 → 首处应对 → 哪些壳用过）

| 特征 | 首处应对 | 用过该手法的壳 |
|---|---|---|
| 1 SMC/自解密 | dump/fix + SoFixer | 梆梆、娜迦、多数加密壳 |
| 2 杀进程不走符号 | syscall-filter + dump 解剖内联 shellcode | 娜迦 |
| 3 self-hook open/write | syscall dump | 梆梆、娜迦 |
| 4 dlopen+dlsym 自解析 | 跟踪运行时自解析 | 娜迦、梆梆 |
| 5 自写 ELF 解析器+自建符号表 | 靠运行时行为定位 | 娜迦 |
| 6 多入口多线程 | 枚举全部入口+看门狗线程 | 娜迦、梆梆 |
| 7 inline hook 检测 | 核心原语恒返回干净 | 梆梆 |
| 8 Frida 痕迹 | 扫描函数恒返回空/隐藏特征 | 娜迦、梆梆 |
| 9 TracerPid/ADB/root/模拟器 | 检测函数恒返回正常 | 娜迦、梆梆、多数壳 |
| 10 检测位图 | 位图汇总判环境干净 | 梆梆 |
| 11 CRC/完整性 | 干掉 CRC 校验/执法分支 | 梆梆、娜迦、多数壳 |
| 12 复用壳自身 API | 借壳已备好的对象做 patch | 娜迦 |
| 13 trace 打印卡死 | 删打印/关重 trace | 通用 |
| 14 检测在早期初始化 | onEnter + 二级锚点 | 娜迦 |
| 15 早期环境探测 | 当最早 hook 锚点 + 属性名过滤 | 娜迦 |
| 16 低地址自毁签名 | 认签名，源头 NOP + 锚整段序列 | 梆梆 |
| 17 反静态门槛 | 容错扫描 + 找解密循环+加密blob | 梆梆 |
| 18 自毁升级 | 按 fault/abort/kill/exit 类兜底 | 梆梆 |
| 19 页0 retstub 环境依赖 | mmap_min_addr=0 + setenforce 0 | 梆梆 |
| 20 多进程看门狗守护 | 先冻看门狗、再冻 main | 梆梆 |
| 21 syscall 走指针表 | seccomp 拦 syscall 入口 | 梆梆 |
| 22 dex 藏 native heap / 选择性加固 | 跳出 dalvik 区，按 endian_tag 锚点 dump | 梆梆 |
| 23 方法级抽取 DEX | 结构校验≠方法恢复，扫 NOP/默认返回骨架，ajm 按 marker 回填 | 爱加密 |
| 24 VM 调度器 / A-table 检测 | 按 caller 区间精确改，结果提取器防误伤 | 爱加密 |
| 25 TracerPid / wchan / ptrace_stop | 对应检测函数逐个 hook 改 0 | 爱加密 |

---

## 边界与注意事项

- 每版壳特征随版本/加固商变化，**上述特征与应对以目标样本实际证据为准**；地址、函数名、偏移需反编译后确认，不能照搬本文数值。
- 特征可叠加；命中多条时逐个匹配、逐个过，不因已过一条就收工。
- 「应对」多数是让检测函数恒返回「干净值」/「end 分支不执行」，属于 patch 目标；patch 前仍须走 `workflow-standards.md` §10 的归属边界与崩溃原因门禁。
- 涉及 Frida 使用前按 `workflow-standards.md` §11 确认 frida-server 状态与版本匹配；不自行更换版本。
- 杀进程/自毁相关：先 syscall-filter 定位 syscall 与 pc/lr/sp 归属，再 dump/fix + 静态分析，未完成前禁止纯动态试错。
- 壳厂商画像为「已学文章」的归纳，遇到新壳/新版本时以样本证据为准，可在此库追加厂商画像或新手法。
