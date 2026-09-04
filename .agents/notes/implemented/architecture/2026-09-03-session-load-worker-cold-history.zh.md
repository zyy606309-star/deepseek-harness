# Agent Note: 会话加载 worker 冷历史

Status: implemented

[English](2026-09-03-session-load-worker-cold-history.md) | 中文

## 问题

一次冷会话历史读取——浏览器打开旧会话，而不激活 Session、不发布 Agent——为了只提供一页有界内容，不得不在宿主上解码并归一化整份 JSONL 日志。宿主在读取期间保留整份解码后的事件数组，而每个想获得有界页的未来消费方都不得不重写分页与冷读校验。

## 决策

`@deepseek-ai/dsh-session-load-worker` 以库而非 Cordis 插件的形式承担冷页读取。`loadSessionPage(request, signal?)` 每次调用启动一个 `node:worker_threads` worker，把请求作为 `workerData` 传入，并以唯一的终态页结算。

worker 用 JSONL 后端自有的冷读原语（来自 `@deepseek-ai/dsh-session-persistence-jsonl/decode` 的 `resolveLogPath`、`readStableFile`、`readPrefixBuffer`）以及来自 `@deepseek-ai/dsh-session-persistence` 的 `snapshotStoredEvents` 与 `assertKnownEventTypes`，解析、读取、解码并归一化日志。完整解码后的事件数组留在 worker 内；跨越消息通道的只有 `ready` 握手、一条 `log` 诊断行，以及一个 `result` 页或 `error` 渲染。

分页镜像 `dsh-host-apiproxy` 的 `paginate`：从窗口尾部向前统计追加来源的 `user/message` 与 `assistant/message` 事件，经 `sourceEventSeqs` 拉入每个被统计消息的分片组，并在最旧被统计组的起始 `seq` 处切分。一页总是一段连续的 `seq` 升序区间，`hasMore = cut > 0`；`beforeSeq` 把窗口尾部前移。

wire 协议是每方向一个 tag 枚举（worker→host 为 `ready` / `log` / `result` / `error`；host→worker 为 `go`），并有 `ready`→`go` 释放闸门，使宿主先挂好监听器再开始工作。宿主在以下情形中取第一个结算：`result` 页、`error` 渲染、worker `error`、结算前 worker `exit`，或中止并终止 worker 的 abort 信号。worker 以清洗后的环境启动——没有环境凭据、`execArgv: []`——只转发 Windows 的 `TMP`/`TEMP` 与未构建引导所需的 `TSX_TSCONFIG_PATH`。已构建入口是 `./worker.cjs`（CommonJS，按路径解析）；未构建形态通过 data-URL 引导装入两个 tsx transform，使源码启动无需预先构建的产物树。

invariant 配套项注册一个空 installer：本包不暴露同进程事件关系，worker 协议与已构建 worker 路径即其边界。

## 考虑过的替代方案

- **冷读取完全留在宿主进程内（当前 api-proxy 路径）。** 否决，这正是本包存在的理由：整份解码日志在读取期间留在宿主内存，而 worker 边界消除的正是这份成本。api-proxy 在暂缓接线落地前保留此路径。
- **把解码后的事件流式传回、在宿主上分页。** 否决：这会把完整日志跨通道传回，重新引入宿主侧的整份日志驻留。
- **在页切点处停止解码。** 否决：打包分片行需从日志前部重建 `seq`/`time`，撕裂尾部恢复要读到末尾，因此 JSONL 格式下无法做到不完整解码的有界跨越。

## 后果

仅支持 JSONL 后端；没有 SQLite 或查询服务读取路径。api-proxy 接线暂缓：网关仍经其自身进程内路径读取冷历史，并不调用 `loadSessionPage`，因此在采纳之前两处分页实现并存，靠评审保持对齐。

每次加载仍扫描完整日志——worker 读取并解码整份产物以定位窗口，然后只回传该页。该边界约束的是每页返回字节数，而非读取或解码字节数，因此超大日志每次冷页读取仍要付出完整解码成本。worker 归一化后的日志随 worker 一并丢弃；跨调用不缓存任何东西，这让每次读取都是一次干净、一次性的解码，但每一页都要重新付出启动与解码成本。

测试驱动未构建 tsx 引导与直接的 worker 源码，并把页窗口对照完整日志、`hasMore`、`beforeSeq`、Zstandard 与原始压缩，以及有界跨越（`JSON.stringify(page)` 绝不携带更早轮次的文本）逐项钉死。
