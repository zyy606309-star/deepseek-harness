# Agent Note: 长会话聊天渲染的窗口化

Status: implemented

[English](2026-09-03-chat-message-list-virtualization.md) | 中文

## Problem

聊天记录通过 `ChatView` 的 `order.map` 渲染每一个关键业务节点，因此一个长会话会为每条 user、assistant、tool 节点各自挂载一个活跃的、独立订阅的 `ChatNodeSeat`。节点数量随会话推进无界增长，而每个 seat 既是一份活跃的 `useSession` 订阅，又是一次可递归展开工具调用树的关键槽位分发。于是多页记录会在 DOM 中同时挂载数千行，即便宿主侧的消息派生（`Session.deriveMessages`）与 surface fold 早已增量化，打开或滚动该会话仍然变慢。trajectory 台账曾遇到同样的问题并用 `@tanstack/react-virtual` 解决；聊天流此前只在 CSS 里留了一行注释，把 `.flowItem` 预留为未来的挂载单元。

## Decision

`ChatView` 在节点数达到 `VIRTUALIZATION_THRESHOLD = 100` 阈值以上时，用 `@tanstack/react-virtual` v3 对关键节点列表做窗口化。达到或超过阈值时，渲染列表是一个 `.virtualWindow`，其子项为绝对定位的 `ChatNodeSeat` 行；低于阈值时保持原来的 `order.map` 普通流不变，因此在占绝大多数的短会话场景下，所有既有的锚点、侧边导航与滚动契约仍读取完整挂载集合。

该窗口是消息列的单个 flex 子项，因此 16px 列间距仍把它与「加载更早」行和尾部装饰分隔开，且子项间距由虚拟化的 `gap: 16` 负责而非列间距（两者绝不叠加）。子项高度可变：`estimateSize: 200` 先给测量设初值，`measureElement` 在浏览器观测到真实高度后再逐项修正。`overscan: 12`、`initialRect` 高度 600（保证首帧非空且可在 jsdom 中测试）以及 `paddingEnd: 16` 补齐尾部空隙。

该虚拟窗口是列的中部子项，而非滚动容器的内容顶部，因此一个 `useLayoutEffect` 测量它相对已解析滚动容器的偏移并作为 `scrollMargin` 传入，使子项起点与可视范围保持相对滚动容器定位，同时让打开态提示与「加载更早」行居于其上方；当这些兄弟元素或视口尺寸变化时由 `ResizeObserver` 重新测量。

滚动容器由既有的 `scrollerOf` 解析：生产环境是祖先 `[data-conversation-scroll]`，单独挂载（测试）时是视图本地的 `.scroll`。窗口化时侧边导航标记位置与 `jumpToUser` 改为基于索引计算（`scrollToIndex`），因为目标行可能尚未挂载；非窗口化路径保留其 DOM 锚点计算。

流式渲染节奏不受本决定影响：assistant 定义已把可见 chunk 按 `animation-frame` 发布，`Notifier.markFrameDirty` 每帧合并一次刷新，因此窗口化只限制挂载集合，不改动流式节奏。

## Alternatives considered

**始终开启窗口化。** 否决：阈值门控让短会话路径与经过验证的旧流逐字节一致，既有滚动/锚点/侧边导航契约及其测试无需全量重写即可保持成立，窗口化分支只在挂载成本真实存在时启用。

**自研窗口而非复用 `@tanstack/react-virtual`。** 否决：该依赖已在工作区内（trajectory 台账使用 v3.14.9），它负责 ResizeObserver 测量、滚动调和与索引对齐，复用它能让两个窗口化界面共用同一套已测量的实现。

**固定行高。** 否决：聊天行承载可变的 markdown、工具卡片与图片，若无 `measureElement`，固定估算值会在子项揭示真实高度后错置滚动位置。

## Consequences

- 长会话的挂载成本由「视口加 overscan」界定，而非由节点总数界定，在不触碰宿主侧增量派生的前提下消除了打开/滚动的主要开销。
- 侧边导航与跳转在窗口化分支增加了基于索引的定位，短会话仍走 DOM 锚点路径；两者均由既有的 `chat-view.client.spec.tsx` 套件覆盖，并新增一条窗口化用例断言挂载节点数低于总数。
- 浏览器 e2e 滚动契约保持「虚拟化中立」：其 DOM 行数探针被替换为滚动容器的 `scrollHeight` 探针，使分页/流式断言测量的是内容增长而非已挂载行数。
