# 小肩膀定制系统

## 目录

- 适用前提
- 一、防检测相关（系统级适配）
- 二、开箱即用功能（无需额外操作）
- 三、需手动启用功能
- dexfix_runner.py（dex/bin 合并 wrapper）

## 适用前提

本节能力仅在目标 Android 设备是**小肩膀定制系统**时可用。每个会话首次涉及整体/抽取式脱壳、任意 so 注入、native 注册监听、定制系统内置 Apatch root 等明确依赖定制系统的工作时，**必须先询问用户当前连接的是否为「小肩膀定制系统」**，并记录答复；这是硬门禁，不是提示项。

`xiaojianbang-syscall-filter` 和 `xiaojianbang-stealth-hook` 不属于小肩膀定制系统能力：它们依赖的是通用 root/su、APatch/KernelPatch、KPM、arm64/GKI 等设备条件。即使用户未确认或否认定制系统，也可以在这些通用前置满足时使用它们。

- 用户确认是定制系统：可使用本节的开箱即用功能、手动启用功能和 `dexfix_runner.py`。
- 用户确认不是，或不确定：不要假设设备具备定制系统能力，按通用流程（Frida、MemDumper、syscall-filter、stealth-hook 等）推进，并在实验记录写明「非定制系统/未确认」。

门禁阻断条件：

- 未向用户确认设备类型：禁止使用整体/抽取式脱壳、任意 so 注入、native 注册监听、定制系统内置 Apatch root、`dexfix_runner.py` 等依赖定制系统能力。
- 用户未回答、回答不确定或确认不是定制系统：禁止把 `libcapture`/`libtrace` 等定制系统迹象当作可用能力依据，只能走通用流程并记录证据缺口。
- 实验记录没有写入用户答复和所选路线：视为门禁未通过，先补记录再继续。

询问示例：

> 当前连接的设备是否为「小肩膀定制系统」？该系统自带整体加固脱壳、抽取式加固脱壳、native 函数注册监听、任意 so 注入和集成 Apatch root，会影响脱壳和定制系统注入工具的选择；syscall-filter/stealth-hook 只看通用 APatch/KernelPatch/KPM/root 条件。

## 一、防检测相关（系统级适配）

定制系统已做系统级反检测适配，分析时可把以下视为环境既有条件，不要误判为目标 App 的检测绕过结果：

- **user 版本**编译，适配 **SELinux Enforcing**。
- 集成 **GMS** 谷歌全家桶。
- 替换 AOSP **test-keys** 为自定义密钥。
- 设备信息伪装为商用 **Pixel 6**。
- **bootloader** 信息伪装为已锁定。
- AOSP 专有 App 替换为 Google App（输入法、图库、相机、搜索、浏览器、WebView 等）。
- WebView 强制可调试。
- 一定程度上防 USB 调试 / WiFi 调试 / 开发者选项检测。
- Java 层防 VPN 检测，改动文件：
  - `libcore/ojluni/src/main/java/java/net/NetworkInterface.java`
  - `packages/modules/Connectivity/framework/src/android/net/NetworkCapabilities.java`
  - `packages/modules/Connectivity/framework/src/android/net/NetworkInfo.java`

注意：这些是系统侧伪装，不代表目标 App 没有自己的设备指纹、root、VPN 或完整性检测。App 自身检测链仍需按常规流程分析。

## 二、开箱即用功能（无需额外操作）

### 调试与签名
- **默认开启 adb**。
- **破解系统签名校验**：修改 App 后无需重签名即可安装。

### 监听 native 函数注册
native 函数注册时在 **logcat** 输出日志，可用于快速定位 RegisterNatives 的 soName、soBaseAddr、funcName、funcAddr 和偏移：

```text
xiaojianbang ArtMethod::RegisterNative soName: <dli_fname>, soBaseAddr: <dli_fbase>,
funcName: <PrettyMethod>, funcAddr: <native_method>, funcAddrNew: <new_native_method>,
offset: <new_native_method - dli_fbase>
```

抓取方式（示例）：

```bash
adb logcat | grep "ArtMethod::RegisterNative"
```

这条日志的 `offset` 是相对 so 基址的偏移，可直接对应 rizin 导出中的函数地址，省去手动 hook RegisterNatives。

### 默认整体加固脱壳
- 脱壳文件路径：`/data/data/<pkgName>/xiaojianbang`
- 目录内容：
  - `.dex` —— 脱壳得到的 dex
  - `.txt` —— 记录 dex 里的类名

整体加固脱壳产物是完整 dex，可直接拉回用 jadx 分析，无需 dexfixer 合并。用 jadx 打开脱壳 dex 时必须关闭 checksum 校验（`jadx -Pdex-input.verify-checksum=no <dex>` 或 gui 关闭 checksum 校验），脱壳产物的校验和常与头部不一致。

## 三、需手动启用功能

### Apatch（内核级 root）
- 内核级 root 方案，已集成。
- 输入**超级密钥**启用，密钥为 `xiaojianbang8888`（即作者微信号）。
- `xiaojianbang-syscall-filter` 的 `load.sh` 和 `xiaojianbang-stealth-hook` 也会使用 KernelPatch superkey（默认值同为 `xiaojianbang8888`，可用 `XJB_KP_SUPERKEY` 覆盖），但这只是通用 KernelPatch/APatch 前置，不代表依赖小肩膀定制系统。

### 任意批量 so 注入
1. 准备 so：文件以 `.so` 结尾，且**不以** `.config.so` 结尾。
2. 推送到 `/data/local/tmp`。
3. 修改 SELinux 上下文：
   ```bash
   chcon u:object_r:app_data_file:s0 <target>
   ```
4. 移动到以下目录，App 自动加载：
   - `/data/local/tmp/xiaojianbang/lib`
   - `/data/local/tmp/xiaojianbang/lib64`

### 抽取式加固脱壳

启用方式：
1. 创建目录 `/data/local/tmp/<pkgName>`（仅用于**启用**抽取式脱壳，本身不是产物目录）。
2. 打开 App，等待约 **1 分钟**，会有线程主动调用函数进行脱壳。
3. 实际产物写入 App 私有目录 `/data/data/<pkgName>/xiaojianbang/`：
   - `.dex` —— 脱壳 dex
   - `.txt` —— 记录 dex 里的类名
   - `.bin` —— 记录函数方法体相关数据

只脱指定类（可选）：
- 创建文件 `/data/local/tmp/<pkgName>/include_classes.txt`。
- 文件内写入类名，**非精确匹配**，仅匹配类名**开头**。
- 不创建该文件则默认脱全部类。

dex 与 bin 合并（关键）：
抽取式脱壳得到的 `.dex` 不完整，方法体数据在 `.bin` 里，必须用 `dexfixer.jar` 把同名 `.dex` 与 `.bin` 合并成完整 dex：

```bash
java -jar dexfixer.jar <dexpath> <binpath> <outpath>
```

| 参数 | 说明 |
| --- | --- |
| `dexpath` | 脱壳得到的 `.dex` 文件路径 |
| `binpath` | 记录方法体数据的 `.bin` 文件路径 |
| `outpath` | 合并后输出的 dex 文件路径 |

## dexfix_runner.py（dex/bin 合并 wrapper）

`scripts/tools/dexfix_runner.py` 封装 `dexfixer.jar`，用于抽取式脱壳产物的批量合并。

Skill 内置：

```text
scripts/tools/dexfixer/dexfixer.jar
scripts/tools/dexfix_runner.py
```

依赖：

- 宿主机 `java`（JRE/JDK）；可用 `XJB_JAVA` 覆盖。
- 批量模式需要 `adb` 和设备 root/su。
- `XJB_DEXFIXER_JAR` 可覆盖 jar 路径，`XJB_ADB` 可覆盖 adb。

批量模式（默认）：自动把设备脱壳目录复制到 `/sdcard` 再拉回，按文件名 stem 配对 `.dex/.bin`，逐对调用 dexfixer 合并。

```bash
python3 scripts/dexfix_runner.py \
  --package com.example.target \
  --out-dir artifacts/dexfix
```

设备脱壳目录默认 `/data/data/<package>/xiaojianbang`（抽取式脱壳的实际产物目录，注意不是 `/data/local/tmp/<package>` 那个启用目录）；如需自定义目录用 `--device-dir`：

```bash
python3 scripts/dexfix_runner.py \
  --package com.example.target \
  --device-dir /data/data/com.example.target/xiaojianbang \
  --out-dir artifacts/dexfix
```

已经手动拉回到本地、只做合并（不走 adb）：

```bash
python3 scripts/dexfix_runner.py \
  --src-dir artifacts/dexfix/pulled \
  --out-dir artifacts/dexfix \
  --no-pull
```

单对合并（透传 dexfixer 原生三参数）：

```bash
python3 scripts/dexfix_runner.py \
  --dex artifacts/dexfix/pulled/classes.dex \
  --bin artifacts/dexfix/pulled/classes.bin \
  --out artifacts/dexfix/classes.fixed.dex
```

注意：

- 批量模式输出文件名为 `<stem>.fixed.dex`，并打印 `dex_total / merged / no_bin / failed` 汇总。
- 只有 `.dex` 没有同名 `.bin` 的，多半不是抽取式脱壳产物（例如整体脱壳的完整 dex），会被跳过并提示，不应强行合并。
- 合并后用 jadx 复核 dex 是否完整、方法体是否还原；合并失败或方法体仍为空时，回到设备确认脱壳是否完成、`.bin` 是否生成。用 jadx 打开合并/脱壳 dex 时必须关闭 checksum 校验（`jadx -Pdex-input.verify-checksum=no <dex>` 或 gui 关闭 checksum 校验），否则合并改动过的 dex 会因校验和不匹配加载失败。
- 拉取时 wrapper 会先用 `su` 把设备脱壳目录 `/data/data/<package>/xiaojianbang` 复制到 `/sdcard/xjb_dexfix_pull/<package>` 再 `adb pull`，结束后清理该 sdcard 临时目录；原始脱壳目录不动。直接 `adb pull /data/data/...` 会因 app 私有目录权限失败，所以必须经 sdcard 中转。
