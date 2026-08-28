# 逆向环境事实（模板）

> 本文是**环境事实快照模板**，不是方法论约束。方法论是通用的，按目标随机应变；这里用占位符说明「每个部署要填什么」，供其他设备 clone 后按各自环境填写（**不要**把本机路径/设备序列提交进仓库）。字段说明见冒号后；方括号 `[...]` 为待填值。

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
| jadx（CLI） | `<JADX_CLI>`，例如 `D:\tools\jadx-1.5.6\bin\jadx-cli.bat` |
| jadx GUI | 不用（可选填 `<JADX_GUI>`） |
| JDK（jadx wrapper 用） | `<JDK17>`，例如 `D:\openjdk-17_windows-x64_bin\jdk-17` |
| 全局 `JAVA_HOME` | `<GLOBAL_JAVA_HOME>`（若太旧会使 jadx 报 class version 错误，用 jadx wrapper 规避） |
| Ghidra | `<GHIDRA_DIR>`，例如 `D:\ghidra_12.0.3_PUBLIC`（伪代码回退，需 JDK 21+） |
| adb | `<ADB_PATH>` 或 PATH；多设备时用 `adb -s <ADB_SERIAL> <cmd>` 指定 |

### jadx 调用约定
```bat
<JADX_CLI> <apk> -Pdex-input.verify-checksum=no ...
```

## 设备端

| 项 | 填写项（`<...>` 为示例） |
|---|---|
| 设备 | `<ADB_SERIAL>`，例如 `11FAFS00000VYM`（Pixel 4 flame） |
| Android | `<ANDROID_VERSION>`，例如 10 |
| ABI | `<ABI>`，例如 arm64-v8a |
| Root | `<ROOT_TYPE>`，例如 Magisk root |
| frida-server 进程名 | `<FRIDA_SERVER_NAME>`，例如 f14 |
| frida-server 版本 | `<FRIDA_VERSION>`，须与宿主一致 |
| APatch / KernelPatch | `<KP_STATUS>`：当前无（是 Magisk）→ syscall-filter、stealth-hook 暂不可用 |

## 当前阶段可用 / 不可用

- **可用**：Frida 链（设备端 server + 宿主一致）、memdumper（有 root）、rizin 反汇编、jadx-cli 反编译。
- **暂不可用（视部署）**：`xiaojianbang-syscall-filter`（需 APatch/KernelPatch + KPM + arm64）、`xiaojianbang-stealth-hook`（需 APatch/KernelPatch + GKI 5.4+ + KPM）、伪代码（rz-ghidra 未装 → 用 Ghidra headless 回退）、小肩膀定制系统能力（整体/抽取式脱壳、任意 so 注入、native 注册监听、内置 Apatch root）。

> 部署方复制本模板、用实际值替换 `<...>`，并把文件名保留为 `environment.md`。工具在 `references/rizin-tools.md`。
