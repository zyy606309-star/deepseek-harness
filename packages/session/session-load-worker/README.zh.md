# @deepseek-ai/dsh-session-load-worker

[English](README.md) | 中文

用于有界会话历史页的 worker 线程冷加载器。JSONL 解码与持久化归一化在 `node:worker_threads` worker 内运行；完整解码后的日志留在 worker 内，只有一页有界内容传回宿主。本包不是 Cordis 插件，也不贡献任何实时会话服务——它是一个库入口（`loadSessionPage`），宿主侧消费方调用它来读取已存储日志，而无需激活 Session 或发布 Agent。

## 用途

`loadSessionPage` 读取一份已持久化的 JSONL 会话日志，返回一个有界历史页。它的存在意义在于：冷历史读取（例如浏览器打开一个旧会话）在一个一次性 worker 内完成解码、校验与归一化，从而不在宿主内存中保留整份日志副本。本包只负责冷页读取：它从不恢复会话、从不向日志追加、也从不组装或发送模型请求。

## 公开 API

`src/index.ts` 导出 `loadSessionPage`、`DEFAULT_MAX_MESSAGES`，以及 `LoadedPage` / `LoadRequest` 类型。

- `loadSessionPage(request, signal?): Promise<LoadedPage>`——每次调用启动一个 worker，把请求作为 `workerData` 传入，并以唯一的终态页兑现。`request` 是 `{ root, compression, id, beforeSeq?, maxMessages }`；`signal` 是可选的 `AbortSignal`，用于终止 worker。
- `DEFAULT_MAX_MESSAGES = 50`——调用方未自行确定时使用的页配额。
- `LoadedPage`——`{ meta: SessionHeader, events: SessionEvent[], hasMore: boolean }`：已存储头部、一段连续的原始事件区间，以及是否有更早历史在该页之前。
- `LoadRequest`——`root`（JSONL 后端的会话根目录）、`compression`（`'zstd' | 'none'`）、`id`（`SessionId`）、`beforeSeq?`（排他下界：只有 `seq` 更小的事件进入窗口；省略时选择完整尾部）与 `maxMessages`（追加来源消息配额）。

没有默认导出，也没有 Cordis 服务。同级 `./invariant` 配套项（`src/invariant.ts`）注册一个空的 installer，其理由说明 worker 协议与已构建 worker 路径是本包唯一的边界。

## 有界页保证

一页总是一段连续的、`seq` 升序的区间，绝不把一个消息切碎。`maxMessages` 从窗口尾部向前统计追加来源的 `user/message` 与 `assistant/message` 事件；每个被统计的消息经 `sourceEventSeqs` 把它的分片组一并拉入，因此切点落在最旧被统计消息组的起始 `seq`。当且仅当 `cut > 0`（更早历史在该页之前）时 `hasMore` 为真；`beforeSeq` 把窗口尾部前移以取得更早的页。无论窗口如何，`meta` 始终携带日志中已存储的 `SessionHeader`。

分页规则与 `dsh-host-apiproxy` 的 `paginate` 一致，因此一旦接线，经此 worker 提供的页与宿主网关的页边界相同。

## Worker 边界

worker 用 JSONL 后端自有的冷读原语（来自 `@deepseek-ai/dsh-session-persistence-jsonl/decode` 的 `resolveLogPath`、`readStableFile`、`readPrefixBuffer`）解析、读取、解码并归一化日志，再应用来自 `@deepseek-ai/dsh-session-persistence` 的 `snapshotStoredEvents` 与 `assertKnownEventTypes`。完整解码后的事件数组留在 worker 内；跨越边界的只有启动 `ready` 握手、一条 `log` 诊断行，以及唯一的 `result` 页或 `error` 渲染。

宿主在以下情形中取第一个结算：`result` 页、`error` 渲染、worker `error`、结算前 worker `exit`，或 abort 信号。worker 以清洗后的环境启动——没有环境凭据、`execArgv: []`——只转发 `TMP`/`TEMP`（Windows）以及未构建引导所需的 `TSX_TSCONFIG_PATH`。已构建入口是 `./worker.cjs`（CommonJS，按路径解析）；未构建形态通过 data-URL 引导装入两个 tsx transform，使源码启动无需预先构建的产物树。

## 取消与错误

- `signal` 中止 worker（`worker.terminate()`）并以 `session load aborted` 拒绝；已中止的信号立即拒绝。
- 缺少产物时以 `session "<id>" has no stored JSONL artifact` 拒绝。
- 解码或校验失败时以 worker 渲染的消息拒绝。
- worker 失败或在结算前退出时，以 `session load worker failed: …` 或 `session load worker exited before settling (exit code N)` 拒绝。

拒绝与兑现恰好结算一次；结算守卫使之后的 message、exit 或 abort 在第一次结算后成为空操作。

## 模型体验

无——本包解码并对已存储的会话日志分页，用于面向客户端的历史读取，不触碰任何提示词、消息、schema、流或工具结果。

#### KV Cache 影响

无；worker 既不组装也不发送提供方请求，其宿主侧消费方为浏览器而非模型读取历史。

## 已知限制与暂缓事项

- **仅支持 JSONL 后端**——`loadSessionPage` 只解析、读取并解码 `session-persistence-jsonl` 产物；没有 SQLite 或查询服务读取路径，因此会话存放在其他后端的部署无法经此 worker 分页。
- **api-proxy 接线尚未接入**——`dsh-host-apiproxy` 仍通过其自身进程内路径读取冷历史，并不调用 `loadSessionPage`；在网关采用它之前，本包是独立库，两处分页实现必须靠评审保持对齐。
- **每次加载仍扫描完整日志**——worker 读取并解码整份产物以定位窗口，然后只回传该页；因此跨越是有限的，但读取与解码开销不是。它按返回字节数是有限的，而非按读取字节数。
