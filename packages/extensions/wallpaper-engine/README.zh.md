---
description: "DeepSeek Harness Web GUI 的 Wallpaper Engine 桥接：Steam 安装发现、清单与媒体路由，以及持久化的效果控件。"
kind: "package-bundle"
---

# @deepseek-ai/dsh-wallpaper-engine

[English](README.md) | 中文

<a id="summary"></a>
## 概述

`dsh-wallpaper-engine` 把本机的 Wallpaper Engine 安装接入 Web GUI。host 半边通过 Steam 的 `libraryfolders.vdf` 定位安装目录、枚举已安装壁纸，并在环回 HTTP 路由上提供清单与媒体/预览字节；浏览器半边把选中的壁纸绘制在应用背后，并暴露效果控件。它不贡献任何模型可见的工具、提示词文本或会话事件。

<a id="table-of-contents"></a>
## 目录

- [使用本包](#use-this-package)
- [理解实现](#understand-the-implementation)
- [进一步探索](#further-exploration)
- [模型体验](#model-experience)
- [已知限制与后续工作](#known-limitations-and-deferred-work)

<a id="use-this-package"></a>
## 使用本包

本包以仓库外 bundle 行的形式加载；一条 patch 条目同时装配两半。

```yaml
- id: wallpaper-engine
  name: '@deepseek-ai/dsh-wallpaper-engine'
```

### 启用已预装的 Web 功能

已在 bundles 里列出本包的 profile 无需额外接线：浏览器半边声明 `platform: web`，因此该行在 headless 或 TUI profile 里同样能加载，只是那时不存在 HTTP 路由。

### 选择与调节壁纸

选中项与四个效果旋钮持久化在 `wallpaper-engine` 设置命名空间中：`id`、`scrim`、`border`、`blur`、`wallpaperBlur`。校验失败的已存段落会回退到默认值，而不会让插件加载失败。

### 路由

- `GET /wallpaper-engine/inventory` 返回 `{ installDir, wallpapers }`。
- `GET /wallpaper-engine/media/<token>` 返回视频或 HTML 字节，支持 `Range`。
- `GET /wallpaper-engine/preview/<token>` 返回预览图。

<a id="understand-the-implementation"></a>
## 理解实现

所有路由都通过插件 fiber 注册，卸载插件即一并撤销。媒体或预览 URL 携带的 token 是绝对路径的 base64url 形式，因此没有任何路由会接受客户端无法从清单中本就获得的文件系统路径。`webServer` 以注入声明、但通过 `ctx.get` 读取，因为同一个 bundle 也会在没有 HTTP 服务的 profile 中加载。Scene（原生 3D）与 Application 壁纸同样会被枚举，但只提供其预览图，因为浏览器无法渲染它们。

<a id="further-exploration"></a>
## 进一步探索

- [`dsh-settings`](../../settings/settings/README.zh.md) 拥有本插件注册并校验的持久命名空间。

<a id="model-experience"></a>
## 模型体验

无：本包是浏览器侧与环回 HTTP 的插件层，不注册任何面向模型的内容。

#### KV Cache effect

无；本包既不组装也不发送 provider 请求。

<a id="known-limitations-and-deferred-work"></a>
## 已知限制与后续工作

- **Scene 与 Application 壁纸只提供预览。** 原生 3D scene 没有可在浏览器中渲染的形式，因此清单只暴露其预览图，媒体路由拒绝它。
- **安装发现是 Steam 形态的。** 插件读取 `libraryfolders.vdf` 并探测 Windows 上常见的 Steam 目录；Steam 之外的安装不会被发现。
- **Steam 探测路径是 Windows 专属的。** 被探测的目录与可执行文件查找都假定 Windows 主机。

<a id="dev-note"></a>
### 开发备注

<details>
<summary>维护者工作上下文——点击展开</summary>

本包是 fork 本地资产：上游不提供 Wallpaper Engine 桥接，因此 bundle 行与包都由本 fork 一起携带。

</details>

**运行时不变式：** 不发布伴生入口。本包不拥有自己的持久状态：选中项存放在它注册的 `dsh-settings` 命名空间里，路由表则是插件 fiber 的 effect。
