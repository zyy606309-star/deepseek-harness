# Agent Note: Retained background job reclamation

Status: implemented

English | [中文](2026-09-03-retained-background-job-reclamation.zh.md)

## Problem

`LocalJobRegistry` kept every job record in memory for the process lifetime, terminal history included. A settled job — `completed`, `killed`, or `failed` — was removed only when its owning agent was disposed or the whole service tore down, so a long-running harness accumulated completed background Bash, PowerShell, PTY, workflow, and one-shot-subagent records without bound. Each record still carries its `output` string, so retention is both a memory leak and a UI-noise source: the assembled conversation renders a "background tasks" list that grows to every completed job the session ever ran, and `job_kill` answers `already-finished` for a record the user cannot otherwise remove.

The [bounded admission note](../bug-fix/2026-08-11-bounded-background-job-admission.md) governs how many live jobs an owner may start and keeps terminal history for that reason; it did not define how long that history may live.

## Decision

`LocalJobRegistry` owns a `completedRetainMs` configuration field (default `60_000`; a negative value retains terminal records forever). Reclamation is **lazy**: every `list`, `get`, and `read` first runs `maybeReclaim()`, which drops a terminal job whose `finishedAt` lies beyond the retention window, then announces each affected owner (or `undefined` for an unowned drop) through `onJobsChanged` so the visible set stays current.

Guards keep the reclamation from breaking the lifecycle contract the [job registry seam](../architecture/2026-07-26-job-registry-seam.md) defines:

- **Reclamation is age-based, not report-based.** The completion notice is delivered by `onJobDone` at settlement, so a settled job is never owed a later delivery; requiring `reported` here would instead leave a settled job whose owner never explicitly `read` it in the store forever. The retention window is the whole guard: a just-finished job stays readable for `completedRetainMs`, then is reclaimed regardless of whether any read marked it reported.
- **Reclamation is lazy, not a timer.** It runs only on the read paths that already observe the store, so it adds no independent timer, no per-job scheduler, and no notification burst outside an already-visible-set change.
- **A job with live waiters is never reclaimed.** A pending `wait` is still obligated to resolve against the terminal snapshot, so it keeps the record even past the window.
- **`completedRetainMs < 0` disables reclamation.** The prior forever-retention behavior stays available for deployments or tests that want it.

## Consequences

- A settled job is retained for the configured window (so the user can still view its result and the completion notice has already been delivered), then reclaimed on the next read path regardless of whether it was ever read. The accumulated history is bounded.
- The UI "background tasks" list shrinks to live plus recently-completed jobs; the assembled conversation no longer renders the full lifetime of finished jobs.
- Existing reads, `already-finished` kills, waits, admission limits, and completion notices inside the retention window are unchanged; the reclaimed-id read path fails loud as an unknown job, matching the pre-existing unknown-id contract.
- A new config `completedRetainMs` is added to the provider schema and typed bundle compose paths, and must be forwarded end to end where `maxConcurrentJobsPerOwner` already is.

## Verification

The `jobs-local` suite adds four cases: a settled job stays within its window; it is reclaimed once the window elapses (the follow-up read fails loud as unknown); a settled job is reclaimed on age even when no read ever reported it; and reclamation announces an owner-granular `onJobsChanged`. The existing admission, ownership, wait, read, kill, notice, and teardown suites all pass unchanged (`test:gui` green, 4008 tests).

## Alternatives considered

**Reclaim immediately on first `reported`.** Rejected because a settled job whose owner never explicitly `read` it stays `reported === false` forever, so report-gated reclamation reintroduces the exact accumulation it is meant to remove; and immediate reclamation would turn `read`, `wait`, and `already-finished` kill into `unknown job` failures, losing a just-finished result the moment it is reported.

**Reclaim on a dedicated timer.** Rejected because a timer adds a process-wide scheduler, a per-job timing table, and a notification cadence that is hard to test and easy to drift. Lazy reclamation runs only on the read paths that already observe the store, so it adds no independent clock and no notification outside a real visible-set change.

**Reclaim regardless of `reported` with no retention window.** Rejected because it would drop a just-finished job before the user (or a completion reporter) can view its result; the retention window keeps the record readable long enough to consume the outcome.
