# xiaojianbang-syscall-filter

> 作者：**小肩膀**　微信：**xiaojianbang8888**

一个工作在 **内核态** 的 APatch/KernelPatch 模块，按 App(UID) 过滤，主要做四件事：

1. **路径检测 trace** —— 记录是谁（调用者 so）、用哪个 syscall、查了什么路径；
2. **伪造返回值** —— 命中 root / frida / xposed / 模拟器特征时返回 `-ENOENT`（文件不存在）；
3. **退出/闪退 trace** —— 记录 `kill/exit/tgkill` 等退出相关 syscall，定位是谁主动杀进程；
4. **内存执行来源 trace** —— 记录 `mmap/mprotect/memfd_create/prctl/clone/ptrace/wait` 等事件，定位匿名执行段、memfd 执行段和 watcher 线程。

因为运行在内核态，目标 App 在用户态无法察觉自己的 syscall 被改写，也无法通过扫描
自身内存发现 hook（对比用户态 inline svc hook，后者容易被反检测代码反查）。

> 想读懂代码实现/改造模块，看 [ARCHITECTURE.md](./ARCHITECTURE.md)。本文只讲怎么用。

---

## 功能特性

- **按 UID 精准过滤**：只对指定 App 生效，其余进程零影响。最多 8 个目标，可运行时增删。
- **四类检测拦截**：ROOT / FRIDA / XPOSED / AOSP(模拟器)，每类可单独开关。
- **命中即伪造**：被检测的 su 路径、注入库、模拟器特征文件统一返回"不存在"。
- **调用者定位**：日志带 `tgid`(进程) / `comm`(线程) / `pc`(svc 位置) / `lr`(调用者)。
- **arm32 App 支持**：同一个 arm64 KPM 同时注册 native syscall table 和 compat syscall table，
  可采集 32 位 App 的 ARM EABI syscall，日志用 `abi:arm32` 标识。
- **内核态解析调用者**：命中当下把 pc/lr 解析成 `so名!偏移`，连秒闪退、fork 即退的
  短命进程、加固壳匿名内存都能定位（这是事后抓 maps 做不到的）。
- **退出/闪退监控**：记录 `exit`、`exit_group`、`kill`、`tkill`、`tgkill`、
  `rt_sigqueueinfo`、`rt_tgsigqueueinfo`、`pidfd_send_signal` 等退出/发信号 syscall，
  包括 `SIGKILL(9)`、`SIGABRT(6)`、`SIGSEGV(11)` 等，并解析触发代码段。
- **内存执行来源监控**：`memmon=on` 后记录 `mmap/mprotect/pkey_mprotect/memfd_create`
  以及 `prctl(PR_SET_VMA_ANON_NAME)`、`clone/clone3`、`ptrace/wait` 等事件，只记录不拦截，
  用于定位匿名 RX/RWX、memfd 执行段和 watcher 线程来源。
- **高价值 syscall 原始采集**：`sysmon=on` 后复用已启用的退出/信号 hook 输出 `[SYS]`
  编号和前 6 个参数；memmon 自身日志已经包含 `mmap/mmap2/mprotect/memfd/clone/ptrace/wait`
  的关键参数，不再额外叠加 `[SYS]`，避免高频内存 syscall 影响稳定性。
- **全量调试模式**：dump 目标 App 访问的所有路径，用于发现规则没覆盖的检测点。
- **运行时控制**：所有开关、目标 UID 都能在不重新加载的情况下动态调整。

---

## 系统要求

- **设备**：已 root，安装 APatch / KernelPatch。实测于 Pixel 6 / Android 13 /
  内核 **5.10 (android13)** / kpver c02。
- **架构**：KPM 本身为 arm64 (aarch64)；支持 arm64 App 和 arm32 compat App。不支持 32 位内核 KPM。
- **加载工具**：设备端 `/data/local/tmp/kpatch`（`load.sh` / `load.ps1` 会检查并自动补齐）。
- **superkey**：APatch 安装时设置的密码，默认 `xiaojianbang8888`，可用 `XJB_KP_SUPERKEY` 覆盖。
- **PC 端**：`adb` + `python3`（解析脚本用）。
- **分发口径**：当前 Skill 工具包只保留 `syscallhook.kpm`、加载脚本和文档，不包含 KPM 源码。

### kpatch 路径约定

scfilter 的 `load.sh` / `load.ps1` 直接调用 KernelPatch/APatch CLI 加载和控制 KPM，所以需要明确
`kpatch` 路径：

| 位置 | 默认路径 | 说明 |
|------|----------|------|
| 设备端 | `/data/local/tmp/kpatch` | `load.sh` / `load.ps1` 实际执行的 CLI |
| Skill 内置副本 | `../kernelpatch-kpatch/kpatch` | 相对 `xiaojianbang-syscall-filter/` 的默认本地来源 |
| 工程安装后副本 | `third_party/kernelpatch-kpatch/kpatch` | `install_skill_tools.py` 复制到工程后的路径 |

若设备缺少 `/data/local/tmp/kpatch`，`load.sh` / `load.ps1` 会从相邻目录
`../kernelpatch-kpatch/kpatch` 自动推送，也可以手动执行 `./load.sh push-kpatch`。
若本地 kpatch 路径不同，用 `XJB_KPATCH_LOCAL=/path/to/kpatch` 覆盖。

---

## 文件作用速查

项目根目录里常用入口就是这 5 个文件：

| 文件 | 作用 | 什么时候用 |
|------|------|------------|
| `load.sh` / `load.ps1` | 推送 kpatch、推送/加载/卸载 KPM，并通过 `ctl` 控制 UID、`fake`、`resolve`、`memmon` 等开关 | 每次加载模块、改配置、查看状态都用它 |
| `capture_test.sh` | 冷启动目标 App，采集一小段 `[scfilter]` dmesg，生成 `raw/hits/resolved` 日志 | 启动期检测、秒闪退、快速回归测试 |
| `capture_live.sh` | 后台流式采集 dmesg，期间手动操作 App，停止后自动分类和解析 | 检测不是启动期触发，需要进页面/点功能时 |
| `scf_snap.sh` | 设备端 maps 快照器，被 `capture_live.sh` 自动 push 到手机后台运行 | `resolve=off` 或需要 maps 兜底解析时用；一般不手动运行 |
| `resolve.py` | 把日志里的 `pc/lr` 解析成 `so!offset` 或 `anon:base+offset`，也能整理内核态 `pcsym/lrsym` | 通常被采集脚本自动调用；手动复查日志时可单独运行 |

一般用户主要用 `load.sh` + `capture_test.sh`。Windows 可用 `load.ps1` 做加载和 `ctl` 控制。
需要长时间操作 App 时再用
`capture_live.sh`；`scf_snap.sh` 和 `resolve.py` 是辅助链路，保留即可。

---

## 快速开始

推荐先用“只观察、不拦截”的稳定配置采集证据。确认规则和调用点无误后，再按需打开 `fake=on`。

```bash
cd ~/bin/xiaojianbang-syscall-filter

./load.sh reload               # 1. 推送并加载模块
./load.sh status               # 2. 确认运行状态

./load.sh ctl 'uidclear'       # 3. 清空旧目标 UID，避免误采
./load.sh ctl 'uidadd=<UID>'   # 4. 加目标 App UID
./load.sh ctl 'fake=off'       # 5. 只观察，不伪造返回（推荐先这样）
./load.sh ctl 'resolve=on'     # 6. 开内核态调用者解析（推荐常开）
./capture_test.sh <tag> 10     # 7. 冷启动快速采集

cat logs/<tag>_resolved.log    # 8. 看结果：路径/内存/syscall 事件 + 调用者 so!偏移
```

需要持续采集并手动操作 App：

```bash
./capture_live.sh <tag> start
#    >>> 拿起手机操作 App：同意隐私协议 → 进主页 → 点功能 <<<
#    （秒闪退的 App 不用操作，等几秒直接 stop）
./capture_live.sh <tag> stop
```

采集完建议收尾：

```bash
./load.sh ctl 'dump=off'
./load.sh ctl 'memdump=off'
./load.sh ctl 'memmon=off'
./load.sh ctl 'sysmon=off'
./load.sh ctl 'exitmon=off'
./load.sh ctl 'uidclear'
```

只想抓启动期/秒闪退，用快速采集：

```bash
./capture_test.sh cbgc 12
cat logs/cbgc_resolved.log
```

### arm32 / 0715quan 示例

`0715quan.apk` 是 32 位样本，包名 `com.quan0715.forum`，UID `10237`，脚本内置 tag 为 `quan`。
稳定采集推荐：

```bash
./load.sh reload
./load.sh ctl 'uidclear'
./load.sh ctl 'uidadd=10237'
./load.sh ctl 'fake=off'
./load.sh ctl 'resolve=on'
./load.sh ctl 'memmon=on'
./load.sh ctl 'sysmon=off'
./load.sh ctl 'exitmon=off'
./capture_test.sh quan 10
cat logs/quan_resolved.log
```

看到 `abi:arm32`、`mmap2`、`off_bytes`、`mprotect`、`memfd_create`、`clone` 等日志，说明 compat
syscall 采集正常。arm32 支持不需要 32 位 KPM：模块仍是 arm64 KPM，通过 compat syscall table
采集 32 位 App。

---

## 定位闪退 / 主动退出

退出监控由 `exitmon` 控制，只记录不拦截。建议同时打开 `resolve=on`，这样进程死前就能把
调用点解析成 `so!偏移` 或 `anon:基址+偏移`。

```bash
./load.sh ctl 'uidadd=<目标UID>'
./load.sh ctl 'resolve=on'
./load.sh ctl 'exitmon=on'
./capture_test.sh <tag> 12
cat logs/<tag>_resolved.log
```

重点看这些事件：

```text
[SIGNAL/SIGABRT(6)/crash=1] tgkill ...
[SIGNAL/SIGKILL(9)/crash=1] kill ...
[EXIT/status=.../0x...] exit_group ...
```

日志里的 `[pc]` 是 syscall 触发点，`[lr]` 通常更接近业务/壳检测逻辑的调用点。匿名加固代码会显示成：

```text
anon:<基址>+0x<偏移>
```

每次启动基址会因为 ASLR 改变，定位时看 `+0x偏移`。

### signed.apk / tuhu 示例

项目根目录的 `signed.apk` 包名是 `cn.TuHu.android`，脚本内置 tag 为 `tuhu`，设备上 UID 为 `10239`：

```bash
./load.sh reload
./load.sh ctl 'uidadd=10239'
./load.sh ctl 'resolve=on'
./load.sh ctl 'exitmon=on'
./capture_test.sh tuhu 8
cat logs/tuhu_resolved.log
```

已复现到的关键结论：

```text
[SIGNAL/SIGKILL(9)/crash=1] kill target_tgid:6005 ...
        [pc] anon:7aa6e94000+0x2bb2c   [lr] anon:7aa6e94000+0x29cb8
```

说明 App 在匿名 native 代码段中主动调用 `kill(pid, SIGKILL)` 杀掉自身；稳定偏移是：

```text
PC: anon + 0x2bb2c
LR: anon + 0x29cb8
```

---

## 定位匿名执行 / memfd / watcher 线程

内存监控由 `memmon` 控制，只记录、不拦截、不修改返回值，不受 `fake=on` 影响。它适合回答这些问题：

- 匿名 RX/RWX 段是谁 `mmap` 出来的；
- 已有内存是谁 `mprotect(PROT_EXEC)` 改成可执行的；
- `memfd_create` 后是否被 `mmap(PROT_EXEC)`；
- `[anon:.bss]` 这类 VMA 名称是谁通过 `prctl(PR_SET_VMA_ANON_NAME)` 设置的；
- watcher 线程、ptrace monitor、waitpid 监控链是谁创建和驱动的。

推荐命令：

```bash
./load.sh reload
./load.sh ctl 'uidadd=10236'
./load.sh ctl 'resolve=on'
./load.sh ctl 'memmon=on'
./capture_test.sh cbgc 12
cat logs/cbgc_resolved.log
```

重点 grep：

```bash
grep -E '\[MEM/EXEC|\[MEMFD|\[MEM/VMA_NAME|\[THREAD/CLONE|\[DEBUG/PTRACE|\[DEBUG/WAIT|\[SIGNAL' logs/cbgc_resolved.log
grep -E 'libDexHelper|anon_name:.bss|fdpath:memfd|ptrace|wait4' logs/cbgc_resolved.log
```

常见标签：

| 标签 | 含义 |
|------|------|
| `[MEM/ANON]` | 匿名映射，常见于堆、线程栈、JIT、壳分配缓冲 |
| `[MEM/EXEC]` | 可执行映射或可执行改权，重点看 `pcsym/lrsym` |
| `[MEM/EXEC|MEM/FD]` | 文件或 memfd 的可执行映射，重点看 `fdpath` |
| `[MEMFD]` | `memfd_create(name, flags)` 返回 fd |
| `[MEM/VMA_NAME]` | `prctl(PR_SET_VMA_ANON_NAME)` 设置 `[anon:name]` |
| `[THREAD/CLONE]` | `clone/clone3` 创建线程或子进程 |
| `[DEBUG/PTRACE]` | `ptrace` 调试/反调试相关调用 |
| `[DEBUG/WAIT]` | `wait4/waitid` 监控子进程状态 |
| `[SYS]` | `sysmon=on` 的高价值 syscall 原始记录，包含 `nr/a0..a5` |

日志里的 `abi:arm64` / `abi:arm32` 用于区分 native syscall table 和 compat syscall table。
arm32 的 `mmap2` 会额外打印 `off_bytes`，避免把页偏移误当成 arm64 `mmap` 的字节偏移。

默认 `memmon=on` 已经会打印高价值事件：匿名映射、可执行映射/改权、memfd、VMA 命名、线程创建、ptrace/wait。日志仍然太多时，先缩短 `capture_test.sh` 时间窗口，或者只看 `logs/<tag>_resolved.log` 中 `lrsym:` 指向目标 so 的行。

需要排查漏项时再打开全量内存调试：

```bash
./load.sh ctl 'memdump=on'
./capture_test.sh cbgc 8
./load.sh ctl 'memdump=off'
```

`memdump=on` 会显著放大日志量，调试完建议关闭 `memdump/memmon/exitmon`。

---

## 命令参考

### load.sh / load.ps1（加载与控制）

| 命令 | 作用 |
|------|------|
| `./load.sh load` / `unload` | 加载设备上已有模块 / 卸载模块 |
| `./load.sh reload` | 重新推送 + 加载（改完代码用） |
| `./load.sh push-kpatch` | 推送内置 kpatch 到设备 `/data/local/tmp/kpatch` |
| `./load.sh status` | 查看当前运行配置 |
| `./load.sh list` / `info` | 列出已加载 KPM / 查看本模块详情 |
| `./load.sh ctl '<命令>'` | 运行时控制，见下表 |

Windows PowerShell 等价命令为 `.\load.ps1 reload`、`.\load.ps1 push-kpatch`、
`.\load.ps1 ctl resolve=on`。

### 运行时控制命令（`ctl`，参数必须是无空格单 token）

| 命令 | 作用 |
|------|------|
| `trace=on` / `off` | 命中打印开关（关掉则静默拦截） |
| `fake=on` / `off` | 伪造返回开关（关掉则只观察不拦截） |
| `dump=on` / `off` | 全量调试：打印目标 UID **所有** path syscall（不止命中的） |
| `resolve=on` / `off` | 内核态解析调用者 so!偏移（推荐开，根治短命进程定位） |
| `exitmon=on` / `off` | 退出/信号 syscall 监控开关，只记录不拦截 |
| `memmon=on` / `off` | 内存/线程/ptrace syscall 监控开关，只记录不拦截 |
| `memdump=on` / `off` | 全量内存 syscall 调试输出；默认 `memmon` 只打印高价值事件 |
| `sysmon=on` / `off` | 高价值 syscall 原始采集开关，只记录不拦截 |
| `ROOT/FRIDA/XPOSED/AOSP=on` / `off` | 分类开关 |
| `uidadd=10299` / `uiddel=10299` / `uidclear` | 动态增删 / 清空目标 UID |
| `status` | 打印当前状态到 dmesg，并由 `load.sh` 显示最近状态行 |

`status` 示例：
```
[scfilter] status: trace=1 fake=0 dump=0 resolve=1 exitmon=0 hooks=0 memmon=1 memhooks=15 memdump=0 sysmon=0 syshooks=0
[scfilter] status_compat: pathhooks=15 exithooks=0 memhooks=17 syshooks=0 compat=1
[scfilter] status_cat: ROOT=1 FRIDA=1 XPOSED=1 AOSP=1
[scfilter] status_uid: uid0=10237 uid1=0 uid2=0 uid3=0
[scfilter] status_uid: uid4=0 uid5=0 uid6=0 uid7=0
```

字段说明：

| 字段 | 含义 |
|------|------|
| `resolve=1` | 日志会带 `pcsym/lrsym`，可直接解析调用者 |
| `exitmon=1` | 退出/发信号事件打印开关已打开 |
| `memmon=1` | 内存/线程/ptrace 事件打印开关已打开 |
| `memdump=1` | 全量内存 syscall 调试输出已打开 |
| `sysmon=1` | 高价值 syscall 原始采集已打开 |
| `hooks=` / `memhooks=` / `syshooks=` | arm64 退出/内存/sysmon hook 注册数量 |
| `status_compat` | arm32 compat syscall table 的 path/exit/mem/sysmon hook 注册数量 |
| `uidN=` | 当前目标 UID 槽位，最多 8 个 |

`status_compat` 里 `compat=1` 才表示当前内核支持 arm32 compat syscall hook；`pathhooks=15`
表示 arm32 path/legacy path 覆盖完整。

### 采集脚本

```bash
./capture_live.sh <tag> start    # 冷启动 App + 流式采集（主力，能抓深层检测）
./capture_live.sh <tag> stop     # 停止 + 分类 + 解析
./capture_test.sh <tag> [秒数]   # 冷启动快速抓（只能抓启动期，不需手动操作）
```

内置 `<tag>`（在 `capture_live.sh` / `capture_test.sh` 顶部 case 增删）：
`cbgc`(川观新闻) `m1905`(1905电影) `sig`(SIGFFCNFN) `khapp`(信泰) `tuhu`(途虎/signed.apk)
`quan`(0715quan.apk/com.quan0715.forum)。

### 新增一个目标 App

```bash
# 1. 查 UID
adb shell su -c "pm list packages -U | grep <包名>"   # 输出 uid:10xxx
# 2. 运行时加入目标
./load.sh ctl 'uidadd=10xxx'
# 3.（可选）在 capture_live.sh / capture_test.sh 顶部 case 加一行 tag
```

### 看日志

采集产物在 `logs/`：

| 文件 | 内容 |
|------|------|
| `<tag>_resolved.log` | **路径命中/退出事件/内存事件 + 调用者 so!偏移** ← 主要看这个 |
| `<tag>_hits.log` | 命中原始记录（含 tgid/tid/comm/pc/lr/sp/signals/mem events） |
| `<tag>_allpaths.log` | dump 模式全量去重路径（找规则未覆盖的检测） |
| `<tag>_allpaths_resolved.log` | 全量路径 + 解析 |
| `<tag>_live_raw.log` | 原始流式日志（最大，可删） |

`capture_test.sh` 会先 `dmesg -C` 清空历史日志，再冷启动 App；它适合启动期检测和秒闪退。
`capture_live.sh` 适合需要手动操作 App 后才触发检测的场景。

也可直接看设备内核日志：`adb shell su -c "dmesg | grep '\[scfilter\]'"`

---

## 配置检测规则

当前分发版不包含 KPM 源码，内置路径规则随 `syscallhook.kpm` 固化发布。日常使用时通过运行时
`ctl` 控制目标 UID 和开关：

```bash
./load.sh ctl 'uidadd=<UID>'
./load.sh ctl 'fake=on'
./load.sh ctl 'root=on'
./load.sh ctl 'frida=on'
./load.sh ctl 'xposed=on'
./load.sh ctl 'aosp=on'
```

如果需要新增或修改默认关键字规则，需要使用源码版重新构建 KPM，再替换本目录的
`syscallhook.kpm`。Skill 分发包只保证当前二进制版本的加载、采集和路径规则开关。

### 选关键词的原则（避免误伤）

1. **够具体**：太短会误伤正常路径。反例 `"su"` 会命中 `/system/usr`、`busybox` 等海量
   正常路径。要用完整路径或带分隔符的 `"/su/"`。
2. **只用于存在性检测**：仅当「App 靠文件存不存在判断」才适合伪造 `-ENOENT`。
   **绝不要**加 `/proc/cpuinfo`、`/proc/self/maps`、`/proc/<pid>/status` 这类——
   它们必然存在、App 读的是**内容**，伪造不存在会刷爆日志且破坏正常功能（见注意事项）。
3. **别加高频系统文件**：会被正常访问命中无数次。

定制系统自带的 `libcapture`、`libtrace` 不在 fake 规则里，默认视为系统侧采集/轮询噪声；不要仅凭这两个字符串判断目标 App 做了 Frida/注入检测。

### 用 dump 模式发现该加哪些规则

```bash
./load.sh ctl 'dump=on'
./capture_live.sh <tag> start
#   操作 App（或等几秒）
./capture_live.sh <tag> stop
./load.sh ctl 'dump=off'

# 从全量路径里挑检测特征
grep -iE 'su|magisk|frida|xposed|riru|zygisk|qemu|nox|emulator' logs/<tag>_allpaths.log | sort -u
# 看调用者：哪些访问来自可疑 so（resolve=on 时）
less logs/<tag>_allpaths_resolved.log
```

把发现的特征记录到实验记录里；需要固化为默认规则时，用源码版重新构建并替换 `syscallhook.kpm`。

### 改默认目标 UID

分发版推荐不改默认 UID，直接用 `uidclear` / `uidadd=` 运行时配置目标。

---

## 源码与重新构建

当前 Skill 分发包已去除 native 源码，只保留必要二进制、加载脚本和使用文档：

```text
syscallhook.kpm
load.sh / load.ps1
capture_test.sh / capture_live.sh / scf_snap.sh
resolve.py
README.md / ARCHITECTURE.md
```

需要改规则、改内核结构体偏移或重新适配内核时，使用源码版构建新的 `syscallhook.kpm`，再放回
本目录并执行 `./load.sh reload`。重新构建时仍必须使用 arm64 KPM 目标；arm32 App 支持来自
compat syscall table，不是 32 位 KPM。

---

## 注意事项

### 能力边界：路径检测有效，内容检测无效

模块只伪造 syscall **返回值**：
- ✅ **路径类检测**（su 路径、模拟器特征文件、注入库文件名）—— 文件存在性检测被骗过。
- ❌ **内容类检测**（读 `/proc/self/maps` 扫内存、`/proc/cpuinfo` 看 CPU 指纹、
  `/proc/<pid>/status` 查 TracerPid 或线程名）—— 文件必然存在，App 看的是内容，
  伪造返回值无效。对抗这类需要 hook read 改写内容（本模块未做）。

### BTF / 内核版本适配（内核态解析）

模块大部分能力跨内核通用，**只有内核态解析（resolve=on）依赖 `vm_area_struct`
字段偏移**。当前二进制的偏移取自本设备 BTF（android13-5.10）：`vm_start=0x0`、
`vm_file=0xa0`。

换设备/内核若 resolve 结果明显错乱，用设备自带 BTF 重新取偏移：
```bash
adb shell su -c "cat /sys/kernel/btf/vmlinux" > /tmp/vmlinux.btf
pahole -C vm_area_struct /tmp/vmlinux.btf | grep -E 'vm_start|vm_file'
# 使用源码版更新 VMA_OFF_* 后重新构建 syscallhook.kpm，再 ./load.sh reload
```

- `vm_start` 是结构体第一字段，跨版本恒为 0；`vm_file` 偏移可能变。
- 加载时 init 日志打印 `resolve syms: get_task_mm=.. find_vma=.. file_path=..`，
  若有 0 说明该符号在此内核名字不同，resolve 自动降级（仍输出裸 pc/lr，可用 PC 端
  maps 解析兜底）。
- `fget/fput` 只用于 `memmon` 解析 `mmap(fd)` 的 fd 路径兜底；缺失时不影响路径拦截、
  退出监控和内存监控主流程，只是部分 `fdpath` 为空或来自 fd 缓存。
- 6.1+ 内核 vma 改用 maple tree，需重新核对偏移。

### 调试模式开销

- `dump=on` 会持续刷大量日志，调试完务必 `dump=off`。
- `resolve=on` 开销很小（只在命中时解析），可常开。
- `exitmon=on` 会额外挂 8 个退出/发信号 syscall，只记录不拦截；定位完可 `exitmon=off`。
- `memmon=on` 会额外挂内存/线程/ptrace 相关 syscall。默认只打印高价值事件，但启动期仍可能有不少日志；定位完建议 `memmon=off`。
- `memdump=on` 会打印全量内存类 syscall，日志量明显大于默认 `memmon`；只适合短时间排查漏项。
- `sysmon=on` 不再额外注册 syscall hook，只复用已启用的 exit/signal hook 打印 `[SYS]`；一般用户可保持 `sysmon=off`。
- 在当前 Pixel 6 测试环境里，`exitmon=on` 以及 `memmon=on + sysmon=on` 曾触发不稳定。稳定采集优先用 `memmon=on sysmon=off exitmon=off`。
- `exit(status=0)` 不一定表示闪退，可能只是普通线程/子进程退出；优先看
  `[SIGNAL/.../crash=1]`、主进程 `exit_group`、以及 `target_tgid` 是否等于当前主进程。

### arm32 兼容边界

arm32 支持指的是 **arm64 Android 内核上的 32 位 App compat syscall**。模块仍然按 arm64 KPM
编译和加载，不生成 32 位内核模块。设备内核若没有 `CONFIG_COMPAT` 或导出不到
`compat_sys_call_table`，`status_compat` 会显示 `compat=0`，arm32 采集会自动降级为不可用。

### 其它

- superkey 默认来自脚本或 `XJB_KP_SUPERKEY`，不要把含真实 superkey 的本地改动外传。
- 加固壳的检测代码常在匿名可执行内存（解析显示 `anon:基址+偏移`）——dump 该段内存
  （`/proc/<tgid>/mem` 从基址起）即可逆向定位检测逻辑。

---

**作者：小肩膀　微信：xiaojianbang8888**
