# Agent Note: 已保留后台任务的回收

Status: implemented

[English](2026-09-03-retained-background-job-reclamation.md) | 中文

## Problem

`LocalJobRegistry` 将每条 job 记录在整个进程生命周期内保留在内存中，包括终止历史。一条已结算的 job——`completed`、`killed` 或 `failed`——只有在其 owner agent 被销毁或整个 service 被拆除时才被移除，因此长时间运行的 harness 会无界累积已完成的 Bash、PowerShell、PTY、workflow 与一次性子代理记录。每条记录仍携带其 `output` 字符串，所以这种保留既是内存泄漏也是 UI 噪音来源：装配后的会话会渲染一个「后台任务」列表，增长到该会话运行过的全部已完成任务，而 `job_kill` 对一个用户无法以其他方式移除的记录回答 `already-finished`。

[有界准入 note](../bug-fix/2026-08-11-bounded-background-job-admission.zh.md) 规定了某个 owner 可启动的实时 job 数量上限，并为此保留终止历史；它并未定义这段历史可以存活多久。

## Decision

`LocalJobRegistry` 拥有一个 `completedRetainMs` 配置字段（默认 `60_000`；负值表示永久保留终止记录）。回收是**惰性的**：每次 `list`、`get` 和 `read` 会先运行 `maybeReclaim()`，它删除一条终止 job——条件是 `finishedAt` 已超出保留窗口——随后通过 `onJobsChanged` 向受影响的 owner（或无主记录时为 `undefined`）广播，使可见集合保持最新。

守卫确保回收不破坏 [job registry seam](../architecture/2026-07-26-job-registry-seam.zh.md) 定义的生命周期契约：

- **回收基于时长，而非 `reported`。** 完成通知由 `onJobDone` 在结算时投递，因此已结算的 job 不再欠后续投递；此处若要求 `reported`，反而会让一条 owner 从未显式 `read` 的已结算 job 永远留在 store。保留窗口本身就是守卫：刚完成的任务在 `completedRetainMs` 内保持可读，随后无论是否有任何读取将其标记为已上报都会被回收。
- **回收是惰性的，而非定时器。** 它只在已观察 store 的读取路径上运行，因此不引入独立定时器、逐 job 调度器，或可见集合变更之外的额外通知突发。
- **仍有存活 waiters 的 job 绝不回收。** 一个挂起的 `wait` 仍有义务针对终止快照解析，因此即使窗口已过也保留其记录。
- **`completedRetainMs < 0` 禁用回收。** 先前的永久保留行为仍可用于需要它的部署或测试。

## Consequences

- 已结算的 job 在配置的窗口内保留（因此用户仍可查看其结果，且完成通知已投递），随后在下一次读取路径上被回收，无论它是否曾被读取。累积历史是有界的。
- UI「后台任务」列表缩小到实时任务加上最近完成的任务；装配后的会话不再渲染已完成任务的完整生命周期。
- 在保留窗口内，既有读取、`already-finished` 的 kill、等待、准入上限以及完成通知均不变；已回收 id 的读取路径会像任何未知 job 一样失败并报 loud。
- 在 provider schema 与类型化 bundle compose 路径中新增 `completedRetainMs`，并且必须在 `maxConcurrentJobsPerOwner` 已经透传的所有位置端到端转发。

## Verification

`jobs-local` 套件新增了四个用例：已结算的 job 在窗口内保留；一旦窗口经过即被回收（随后的读取失败并报 unknown）；已结算的 job 即使从未被读取上报也会在超时后被回收；以及回收会广播 owner 粒度的 `onJobsChanged`。既有的准入、owner、等待、读取、kill、通知与 teardown 套件在改动前后全部通过（`test:gui` 全绿，4008 项测试）。

## Alternatives considered

**首次上报时立即回收。** 否决：一条 owner 从未显式 `read` 的已结算 job 会永远保持 `reported === false`，因此以 `reported` 设门槛的回收会重新引入它本要消除的累积；而立即回收会在它被上报的瞬间把 `read`、`wait` 与 `already-finished` 的 kill 变成 `unknown job` 失败，丢失刚完成的结果。

**用独立定时器回收。** 否决：定时器会增加进程级 scheduler、逐 job 计时表，以及难以测试、容易漂移的通知节奏。惰性回收只在已观察 store 的读取路径上运行，因此不引入独立时钟，也不产生真实可见集合变更之外的通知。

**不分报告状态、且无保留窗口一律回收。** 否决：它会在用户（或完成 reporter）仍能查看结果前就丢弃刚完成的 job；保留窗口让记录在足够长的时间内保持可读，以便消费其结果。
