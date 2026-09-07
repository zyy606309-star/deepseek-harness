# 逆向环境事实（模板）

> 本文是**环境事实快照模板**，不是方法论约束。方法论是通用的，按目标随机应变；这里用占位符说明「每个部署要填什么」，供其他设备 clone 后按各自环境填写。本机型已记录当前部署的两台设备（见「设备端」），字段说明见冒号后；方括号 `[...]` 为待填值。

## 宿主机

| 工具 | 填写项（`<...>` 为示例） |
|---|---|
| Python 解释器 | `<VENV_PYTHON>`，例如 `D:\网易\.venv\app-reverse-lab\Scripts\python.exe` |
| frida | `<FRIDA_VERSION>`，须与设备端 server 一致 |
| frida-tools | `<FRIDA_TOOLS_VERSION>` |
| capstone | `<CAPSTONE_VERSION>` |
| unicorn | `<UNICORN_VERSION>` |
| keystone-engine | `<KEYSTONE_VERSION>` |
| rizin | `<RIZIN_PATH>`，例如 `C:\Program Files\Rizin\bin\rizin.exe`；**反汇编** |
| rz-ghidra（伪代码） | `<RZ_GHIDRA_STATUS>`：未装（官方仅源码包、无 Windows 预编译）→ 伪代码走 Ghidra headless |
| garlic（Java 反编译首选） | `<GARLIC_PATH>`，例如 `D:\garlic-build\garlic-main\build\garlic.exe`；C 实现、秒级反编译 apk/dex/class/jar |
| garlic `-n`（ELF 分析） | 默认不用；仅用户明确要求时用（Windows 上 `librosemarylib.dll` 运行时加载有依赖坑） |
| jadx（Java 反编译回退） | `<JADX_CLI>`，例如 `D:\tools\jadx-1.5.6\bin\jadx-cli.bat` |
| jadx GUI | 不用（可选填 `<JADX_GUI>`） |
| JDK（jadx wrapper 用） | `<JDK17>`，例如 `D:\openjdk-17_windows-x64_bin\jdk-17` |
| 全局 `JAVA_HOME` | `<GLOBAL_JAVA_HOME>`（若太旧会使 jadx 报 class version 错误，用 jadx wrapper 规避） |
| Ghidra | `<GHIDRA_DIR>`，例如 `D:\ghidra_12.0.3_PUBLIC`（伪代码回退，需 JDK 21+） |
| adb | `<ADB_PATH>` 或 PATH；多设备时用 `adb -s <ADB_SERIAL> <cmd>` 指定 |

### garlic 调用约定（Java 反编译首选）
```bat
<GARLIC_PATH> <apk> -o <out_dir> -t 4
<GARLIC_PATH> <apk> -s          # 输出 smali（可选）
<GARLIC_PATH> <apk> -g          # 生成调用图（可选）
```
> garlic 无需关 dex checksum（无 jadx 的 checksum 坑）。默认不用 `-n`；仅用户明确要求时才用。garlic 不可用时回退 jadx。

### jadx 调用约定（回退）
```bat
<JADX_CLI> <apk> -Pdex-input.verify-checksum=no ...
```

## 设备端

### 定制系统设备（可用全部定制系统能力）

| 项 | 填写项 |
|---|---|
| 设备 | `19051FDF60018V`（小肩膀定制系统设备） |
| Android / ABI | 已刷小肩膀定制系统（user 版、SELinux Enforcing、伪装 Pixel 6、内置 APatch root） |
| Root | 定制系统内置 APatch 内核级 root（超级密钥 `xiaojianbang8888`） |
| frida-server 进程名 | `<FRIDA_SERVER_NAME>`（定制系统，例如 f14） |
| frida-server 版本 | `<FRIDA_VERSION>`，须与宿主一致 |

> 该设备可用于：整体/抽取式脱壳、任意 so 注入、native 注册监听、`dexfix_runner.py` 合并、定制系统内置 Apatch root。`syscall-filter`/`stealth-hook` 也可用（APatch/KernelPatch 前置满足）。

### 普通用户态 root 设备

| 项 | 填写项 |
|---|---|
| 设备 | `11FAFS00000VYM`（Pixel 4 flame） |
| Android | 10 |
| ABI | arm64-v8a |
| Root | Magisk root（无 APatch/KernelPatch） |
| frida-server 进程名 | `f14` |
| frida-server 版本 | `<FRIDA_VERSION>`，须与宿主一致 |
| APatch / KernelPatch | 无 → `syscall-filter`、`stealth-hook` 暂不可用 |

> 该设备只有通用 root：Frida 链、memdumper（有 root）、rizin 反汇编、garlic/jadx 反编译、`SoFixer` 修复；**不**具备定制系统能力，也无 APatch/KernelPatch（无 KPM/GKI）。

## 当前阶段可用 / 不可用

> 按「当前连接的设备」判定，任务中用户会说明使用哪台。

- **定制系统设备（`19051FDF60018V`），以下全部可用**：整体加固脱壳、抽取式脱壳（+ `dexfix_runner.py` 合并）、任意 so 注入、native 注册监听、定制系统内置 Apatch root、syscall-filter、stealth-hook（APatch/KernelPatch + GKI 满足）；Frida 链、memdumper、rizin 反汇编、garlic/jadx 反编译。
- **普通 root 设备（`11FAFS00000VYM`）**：Frida 链、memdumper（有 root）、rizin 反汇编、garlic 反编译（Java 层首选）、jadx-cli 反编译（回退）。**不**具备定制系统能力，**无** syscall-filter/stealth-hook（缺 APatch/KernelPatch）。
- **通用暂不可用**：伪代码（rz-ghidra 未装 → 用 Ghidra headless 回退）、garlic `-n` ELF 分析（Windows 上 librosemarylib dll 依赖坑）。

> 部署方复制本模板、用实际值替换 `<...>`，并把文件名保留为 `environment.md`。工具在 `references/rizin-tools.md`。
