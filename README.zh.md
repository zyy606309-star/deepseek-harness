# DeepSeek Harness（个人 fork）

[English](README.md) | 中文

本仓库是 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（`dsh`）的个人 fork。上游是一个基于 [Cordis](https://github.com/cordiverse/cordis)、以「一切皆插件」构建的开源 agent harness。本 fork 跟随上游 `0.1.5-rc.2` 线，并附带下面列出的增补；此处未点名的包都是该版本的上游代码。

上游文档、指南与插件目录见 [deepseek-harness.github.io](https://deepseek-harness.github.io/deepseek-harness/)。

## 这个 fork 增加了什么

### 会话时间线

[`@deepseek-ai/dsh-session-timeline`](packages/session/session-timeline/README.zh.md) 为持久化 Session 增加回退、删除、重新生成，输入框压缩按钮，以及可选地从持久检查点恢复工作区文件。删除或回退某一轮会**真正截断尾部**：[`Session.truncate`](packages/core/session/README.zh.md) 与两个持久化后端会把被移除事件从活 Session 和当前 generation 中删掉，而不是写一个 surface 标记。

### 会话交接

会话行「…」菜单可以复制会话 ID，Web profile 挂载了 [`tool-session-query`](packages/session-query/tool-session-query/README.zh.md)，于是新会话能检索并读取交接过来的那个会话。

### 更省的历史读取

[`packages/session/session-persistence-jsonl`](packages/session/session-persistence-jsonl/README.zh.md) 为一页历史只解码一段连续的日志尾部，而不是还原整份产物；因此打开很长的历史会话不再构建完整对象图，Session 控制器也能在不激活 agent 的情况下提供冷会话分页。

### 压缩修复

[`compaction-basic`](packages/compaction/compaction-basic/README.zh.md) 按 Session **即将使用**的模型计价 pre-step 压力；摘要撞到生成上限时也会保留已产出的文本。

### 本地壁纸

[`@deepseek-ai/dsh-wallpaper-engine`](packages/extensions/wallpaper-engine/README.zh.md) 把本机 Wallpaper Engine 渲染在 Web GUI 背后，并持久化其效果控件。

### 逆向 preset

内置的 [`reverse`](apps/cli/config/agent-presets/reverse/preset.yml) agent preset 携带 [`xiaojianbang-auto-reverse`](.agents/skills/xiaojianbang-auto-reverse/SKILL.md) 技能，并挂载 [`crawler-mcp`](crawler-mcp/README.md) 这个 Model Context Protocol server，用于 CDP 驱动的浏览器、网络与 JavaScript 逆向工作。

<a id="run"></a>
## 运行这个 fork

<a id="run-from-source"></a>
### 从源码运行

```sh
git clone https://github.com/zyy606309-star/deepseek-harness.git
cd deepseek-harness
pnpm install
pnpm run build
pnpm dsh --profile web web
```

`pnpm run build` 准备仓库产物，`pnpm dsh` 直接使用这些产物、不再重新构建。Web UI 会打印带一次性 token 的启动 URL；打开该 URL 后浏览器才会得到后续请求需要的会话 cookie。

## 跟随上游

`origin` 是本 fork，`upstream` 是 `deepseek-ai/deepseek-harness`：

```sh
git fetch upstream
git merge upstream/master
pnpm install
```

## 这个 fork 的已知限制

- **未开开发者模式的 Windows。** 无法创建符号链接，因此基于 symlink 的用例会以 `EPERM` 失败，`apps/cli/tests/profiles/acp/cordis.yml` 也会被检出成一个内容是目标路径的文本文件。
- **fork 上的 Actions secret。** `E2E (real DeepSeek API)` 与 installed-wheel 作业需要仓库 secret `DEEPSEEK_API_KEY_EXTERNAL`；缺了它这些作业会在 preflight 阶段失败，而不是自行跳过。
- **逆向 preset 与本机绑定。** 它的技能与 MCP 条目带绝对 Windows 路径，换主机需要重新指向。
- **历史被重写过。** 分支 `archive/remote-master-2026-09-13` 保存 `0.1.5` 之前的 fork 血统；仍停在那条血统上的克隆要用 `git fetch origin && git reset --hard origin/master` 同步，而不是 pull。

## 开发

从[开发指南](docs/development.zh.md)与[架构文档](docs/architecture.zh.md)开始。agent 遵循 [AGENTS.md](AGENTS.md)；贡献规则见 [CONTRIBUTING.zh.md](CONTRIBUTING.zh.md)。

## 许可证

[MIT](LICENSE)。上游版权与第三方依赖许可披露于 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
