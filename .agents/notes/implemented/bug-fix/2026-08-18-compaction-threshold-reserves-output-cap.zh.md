# Agent Note: 压缩压力阈值预留模型的输出上限

Status: implemented

[English](2026-08-18-compaction-threshold-reserves-output-cap.md) | 中文

## 问题

`compaction-basic` 把压力阈值按模型完整的合并上下文窗口来计价（`floor(contextWindow × thresholdRatio)`），却忽略了每个对话请求都会声明一个输出预算（`max_tokens`，在 DeepSeek 适配器上默认 256,000）。提供方的上下文窗口是「输入加输出」的合并上限，因此在下一个请求——重放的历史加上预留的输出——超过窗口之前，历史只能占用 `contextWindow − max_tokens`。

在出厂默认值下——1,000,000 的窗口、256,000 的输出上限、`0.8` 的阈值——压缩要等到 800,000 token，而有效输入预算只有 744,000。于是对话在 744K–800K 区间内就溢出了，压缩根本来不及触发。提供方在没有 `[DONE]` 的情况下关闭 SSE 流，抛出 `STREAM_CLOSED`；它既不是 `CONTEXT_WINDOW_EXCEEDED`（因此溢出恢复路径忽略它），也不在默认可重试集合里（因此 `dsh-llm-retry` 不重试）——最终变成一次终止性的轮次失败。

## 决策

`resolveCompactSpec` 现在接收适配器的单请求输出上限（来自 `resolveModelInfo` 的 `defaultMaxTokens`），并按有效输入预算对压力阈值计价：`floor((contextWindow − outputCap) × thresholdRatio)`。保留（retention）仍按完整窗口计价，因为保留尾部表达的是「逐字保留多少近期历史」，与输出空间无关。省略、非整数、非正数或大于等于窗口的输出上限都会回退到完整窗口，从而对不报告上限的适配器保持原有行为。

在出厂默认值下，阈值变为 `floor(744,000 × 0.8) = 595,200`，因此压缩会在对话仍为预留输出留有余量时触发。

## 备选方案

**降低默认 `thresholdRatio`（0.8 → 0.6）。** 能修好出厂默认值，但对其输出上限占窗口比例不同的任何模型仍留下同样的缺陷，并且悄悄改变了部署针对完整窗口所配置的那个值。被否决，改为直接对预留量计价。

**预留一个估算输出，而不是适配器完整的 `max_tokens`。** 一个对话步骤通常远低于上限输出，因此预留完整上限偏保守，会比严格必要的时间更早压缩。被否决，因为提供方检查的是请求声明的 `max_tokens` 与合并窗口的关系，而不是最终输出；预留更少仍可能让请求超过窗口。

**把 `STREAM_CLOSED` 当作压缩触发条件或可重试失败。** DeepSeek 适配器有意把干净的半截 EOF 归类为不可重试的 `STREAM_CLOSED`（被截断的响应没有可信的结束标记），而重试同一个超大的请求也于事无补。溢出恢复路径已经处理了提供方干净的 `CONTEXT_WINDOW_EXCEEDED`。被否决；正确的修复是避免走到提供方截断的那一步。

## 影响

压缩现在会在任何报告了单请求输出上限的模型上更早触发——在出厂 DeepSeek 默认值下是 ~595K 而不是 ~800K。其提供方不会按合并窗口预留 `max_tokens` 的部署，可通过从适配器省略该上限来保持旧时机。`ResolvedCompactSpec.contextWindow` 仍报告完整窗口，而 `thresholdTokens` 反映预留后的预算，因此只拿 `thresholdTokens` 与占用率比较的读取方不受影响。

## 测试

`packages/compaction/compaction-basic/tests/compaction-basic.spec.ts` —— `resolveCompactSpec` 按 `contextWindow − outputCap` 对阈值计价，并在省略、非整数、非正数及大于等于窗口的上限情况下回退到完整窗口；一个集成用例证明 `compactIfNeeded` 会从 `resolveModelInfo` 读取 `defaultMaxTokens`，并压缩一个停留在无预留阈值之下的夹具。
