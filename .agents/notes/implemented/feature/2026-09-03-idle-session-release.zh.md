# Agent Note: 空闲会话释放（卸载常驻内存）

Status: implemented

[English](2026-09-03-idle-session-release.md) | 中文

## Problem

Web GUI 接触过的每个普通会话都会变成一个常驻的 `Agent` + `Session`，其完整事件日志在整个进程生命周期内一直留在宿主的 V8 堆里。客户端的 `Session.dispose()` 是文档写明的 no-op（"session instances remain resident"），切走一个会话也绝不会 detach 它。于是长期运行的宿主会累积每个会话的完整历史，全部挤在一个单线程的 Node 堆里；堆越大，V8 major GC 暂停越久，整个事件循环都会卡住——这就是前端报告的"整体卡"，而 PyCharm、Chromium（JVM／多进程，GC 都是并发的）却依然流畅。

## Decision

`session.dispose` 是一个新的 wire 方法。它把一个**存活但空闲**的会话从宿主内存中释放，却不碰它的持久化 JSONL 日志：停止并注销 agent、detach 会话、让事件日志可被 GC。正在运行（有活跃 turn）的会话会以 `session-busy` 拒绝，因此绝不会在任务中途被拆除；session 支持的子代理以 `agent-busy` 拒绝。

拆除复用现有的 `AgentHandle.dispose()` 能力——那是唯一能停掉循环、等待静默、先 detach agent 再 detach session、并解绑 scope 的拥有者（[agent 生命周期契约](../architecture/2026-06-18-agent-lifecycle-and-ownership-contracts.zh.md)）。读取时恢复冷会话的解析器（`createApiRemoteAgentResolver`）现在把每个已解析的 `AgentHandle` 保留在一个按 id 的 map 里，并暴露 `dispose(sessionId)` 来排空并遗忘它，这样会话就能从当初物化它的同一条路径被释放。客户端的 `Session.dispose()` 转发到 wire，工作区行菜单只在空闲行上暴露"释放会话"（`running` 或有运行中的后代时隐藏）；释放后客户端重新拉取列表，让该行作为冷（未加载）会话保留，而不是闪一下消失。

## Consequences

- 释放 `逆向模式开发与优化` 这类会话（大、空闲、之前打开过）会缩小宿主堆、缩短 V8 GC 暂停——这是针对单线程卡顿的低成本、精准修复，而不是多进程重写。
- 持久化日志不受影响：会话仍在列表里、下次打开重新加载、什么都不丢。
- 运行中的会话绝不能被释放（`session-busy`），UI 对运行中的行隐藏该动作，因此活跃长任务绝不会被这条路径拆除。
- 解析器现在为每个恢复的会话在整个宿主生命周期内保留一个 `AgentHandle`（此前被丢弃的能力），这是一个以存活会话 id 为键的小型有界 map，`dispose` 时清除。

## Verification

`session.dispose` 通过 fetch 载体端到端覆盖（schema、dispatch、value schema、fixture）以及宿主 proxy（空闲释放、运行中的 `session-busy`、子代理 ownership fence）。`createApiRemoteAgentResolver` 测试钉住了"已解析 handle 被保留并释放"。客户端 runtime/connection/workspace 套件保持全绿（六个被改包共 1252 项测试），typecheck 通过。

## Alternatives considered

**按内存阈值或空闲超时自动淘汰。** 暂不采用：自动策略必须完美区分"正在运行的 turn"与"空闲会话"，一旦误判就会拆除一个活跃长任务。手动释放让用户精确掌控，并以"运行中行隐藏该动作"作为强制，同时为未来的自动策略留出空间而不引入风险。

**对 session store 做多进程／worker 线程隔离。** 不先采用：那是对内存内 session/projection/scope 图的核心重写，爆炸半径大，且不是针对所观察到的 GC 暂停卡顿的精准修复。释放空闲常驻会话能直接缩小堆，是低成本的第一步；出进程隔离仍是另一个更大的方向。

**截断内存内事件日志（只保留折叠后的 surface）。** 不采用：append-only 日志是重放、导出、分叉和模型上下文都依赖的持久化事实来源，截断会破坏重建。按需释放整个常驻 agent 才是正确的单位。
