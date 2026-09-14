# Agent Note: 活动日志被改写后重新折叠 token 计量

Status: implemented

[English](2026-09-14-token-meter-refold-after-log-rewrite.md) | 中文

## Problem

在一个与压缩无关的状态都没变过的会话里，`/compact` 报出 `compaction: token-meter surface does not match the current session surface`。此前该会话刚执行过一次回退。

meter 为每个 Session 维护一份按位置回放的状态，游标 `consumedEvents` 以 `while (consumedEvents < session.seq)` 推进。回退或删除轮次会通过 `Session.truncate` 就地改写活动日志，而它只重置 Session 自己的 surface 折叠、不追加任何事件。因此凡是用「游标是否落后于 `session.seq`」判断新鲜度的消费方都会漏掉这次改写：日志变短后循环体不再可达，状态继续为日志里已不存在的事件计价。压缩侧的 `selectCompactableRange` 会把 meter 的节点集与 `session.surface.nodes` 对比，于是这个陈旧节点让手动压缩在事务开启前就抛出，也让自动压力压缩以同样方式失败、只沦为 step 前的一条警告。截断到零事件时该状态会无限期保留。

## Decision

`ReplayState` 额外记住最后折叠的那个事件。一旦 `consumedEvents - 1` 位置上的事件不再是它，`_sync` 就从 seq 0 重新折叠——这是唯一能在 O(1) 内识别「就地改写前缀」而非「游标只是落后于尾部」的判据。该同一性检查不需要改动 Session API，也不需要截断通知。

## Alternatives considered

**把游标与 `session.seq` 比较。** 不予采纳：日志变短会降低 `session.seq`，`consumedEvents > session.seq` 能覆盖常见情形，却会漏掉「只删掉一个事件、随后日志又长回游标之上」的改写。

**在 `measure()` 内对比 `session.surface.nodes` 发现分歧。** 不予采纳：它重复了消费方已有的比较，让每次测量都为它付费，而且是掩盖被改写的前缀，而不是修复它。

**由 `Session` 向观察者广播截断。** 本次修复不予采纳：观察面只有 `session/event` 与 `session/disposed`，新增截断通知等于新增一套公开的会话生命周期面，需要自带文档、不变式与 SDK 投影。同一性检查无需它即可修好计量这一方。

## Consequences

回退之后的测量描述的是变短后的日志，`/compact` 因此恢复可用。被改写的日志要付一次完整重折叠的代价，已作为包 README 的限制条目记录。[token-meter 测试](../../../../packages/llm/token-meter/tests/token-meter.spec.ts) 钉住日志变短后的重折叠、清空日志的情形，以及格式错误事件仍保持的可重复性。

`SessionProjectionRegistry.advanceCell` 判断活动 cell 新鲜度用的是同一种方式，因此日志被改写后，meter 的三个投影单元会继续报告回退前的值，直到其 cell 被重建。本记录修的是 `measure()`——压缩与压力决策读取的正是它；投影这条路径仍然敞开。
