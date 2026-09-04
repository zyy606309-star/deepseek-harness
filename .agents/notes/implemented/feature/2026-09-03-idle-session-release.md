# Agent Note: Idle session release (unload resident memory)

Status: implemented

English | [中文](2026-09-03-idle-session-release.zh.md)

## Problem

Every ordinary session the web GUI touches becomes a resident `Agent` + `Session` whose full event log stays in the host's V8 heap for the process lifetime. The client's `Session.dispose()` is a documented no-op ("session instances remain resident"), and switching away from a session never detaches it. A long-lived host therefore accumulates every session's complete history in one single-threaded Node heap; as the heap grows, V8 major GC pauses lengthen and the whole event loop stalls — the "整体卡" the web frontend reports while PyCharm and Chromium (JVM / multi-process, both GC-concurrent) stay responsive.

## Decision

`session.dispose` is a new wire method. It releases a **live but idle** session from host memory without touching its durable JSONL log: it stops and unregisters the agent, detaches the session, and lets the event log be garbage-collected. A running session (an active turn) rejects with `session-busy` so a mid-task teardown can never happen; session-backed subagents reject with `agent-busy`.

The teardown reuses the existing `AgentHandle.dispose()` capability — the only owner that stops the loop, awaits quiescence, detaches agent then session, and unwinds the scope ([agent lifecycle contract](../architecture/2026-06-18-agent-lifecycle-and-ownership-contracts.md)). The resolver that resumes cold sessions on read (`createApiRemoteAgentResolver`) now retains each resolved `AgentHandle` in a per-id map and exposes a `dispose(sessionId)` that drains and forgets it, so a session can be released from the same path that materialized it. The client's `Session.dispose()` forwards to the wire and the workspace row menu exposes "释放会话" only on idle rows (`running` or running descendants hide it); after release the client re-pulls the list so the row stays as a cold (unloaded) session instead of blinking out.

## Consequences

- Releasing `逆向模式开发与优化`-style sessions (large, idle, previously opened) shrinks the host heap and shortens V8 GC pauses — the low-cost, targeted fix for the single-threaded lag, instead of a multi-process rewrite.
- The durable log is untouched: the session stays listed, re-loads on the next open, and loses nothing.
- A running session can never be released (`session-busy`), and the UI hides the action for running rows, so an active long task is never torn down by this path.
- The resolver now retains one `AgentHandle` per resumed session for the host lifetime (the capability it previously discarded), which is a small bounded map keyed by live session id and cleared on `dispose`.

## Verification

`session.dispose` is covered end-to-end through the fetch carrier (schema, dispatch, value schema, fixture) and the host proxy (idle release, `session-busy` for running, subagent ownership fence). `createApiRemoteAgentResolver` tests pin that a resolved handle is retained and released. Client runtime/connection/workspace suites stay green (1252 tests across the six touched packages), and typecheck passes.

## Alternatives considered

**Auto-evict on a memory threshold or idle timeout.** Rejected for now: an automatic policy must distinguish a running turn from an idle session perfectly, and a misjudgement tears down a live long task. Manual release gives the user exact control with the running-row guard as enforcement, and leaves the door open for a future policy without the risk.

**Multi-process / worker-thread isolation of the session store.** Rejected as the first move: it is a core rewrite of the in-memory session/projection/scope graph, high blast radius, and not a targeted fix for the observed GC-pause lag. Releasing idle residents shrinks the heap directly and is the low-cost first step; out-of-process isolation remains a separate, larger direction.

**Truncate the in-memory event log (keep only the folded surface).** Rejected because the append-only log is the durable source of truth that replay, export, fork, and model context all derive from; trimming it would break reconstruction. Releasing the whole resident agent on demand is the correct unit instead.
