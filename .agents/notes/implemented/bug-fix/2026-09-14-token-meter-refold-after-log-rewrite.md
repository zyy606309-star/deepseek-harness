# Agent Note: Refold token measurement after a live log rewrite

Status: implemented

English | [中文](2026-09-14-token-meter-refold-after-log-rewrite.zh.md)

## Problem

`/compact` failed with `compaction: token-meter surface does not match the current session surface` in a session where nothing about compaction had changed. A rewind had removed a turn first.

The meter keeps one positional replay state per Session behind a consumed-event cursor it advances with `while (consumedEvents < session.seq)`. A rewind or a turn deletion splices the live log through `Session.truncate`, which resets the Session's own surface fold but appends no event. Any consumer that decides staleness by comparing its cursor against `session.seq` therefore misses the rewrite: a shrunk log makes the loop body unreachable, so the state keeps pricing events the log no longer holds. Compaction's `selectCompactableRange` compares the meter's node set against `session.surface.nodes`, so the stale node made manual compaction throw before its transaction opened, and made automatic pressure compaction fail the same way into a pre-step warning. Truncating to zero events retained the state indefinitely.

## Decision

`ReplayState` also stores the event it folded last. `_sync` refolds from seq 0 whenever that event is no longer the one at `consumedEvents - 1` — the only O(1) test that detects an in-place prefix rewrite rather than a cursor merely behind the tail. The identity check needs no Session API change and no truncation notification.

## Alternatives considered

**Compare the cursor against `session.seq`.** Rejected: a shrunk log lowers `session.seq`, so `consumedEvents > session.seq` catches the common case but misses a rewrite that removes one event before the log grows back past the cursor.

**Detect divergence from `session.surface.nodes` inside `measure()`.** Rejected: it duplicates the consumer's comparison, charges every measurement for it, and hides a rewritten prefix instead of repairing it.

**Announce truncation from `Session` to observers.** Rejected for this fix: the observation surface carries only `session/event` and `session/disposed`, so a truncation notification is a new public session lifecycle surface with its own docs, invariants, and SDK projections. The identity check repairs the measurement owner without it.

## Consequences

Measurements taken after a rewind describe the shortened log, so `/compact` works again. A rewritten log costs one full refold, recorded as a package README limitation. [token-meter specs](../../../../packages/llm/token-meter/tests/token-meter.spec.ts) pin the shrunk-log refold, the emptied-log case, and the unchanged repeatability of a malformed event.

`SessionProjectionRegistry.advanceCell` decides live-cell staleness the same way, so a rewritten log leaves the meter's three projection units reporting pre-rewind values until their cells are rebuilt. This note's fix covers `measure()`, which is what compaction and pressure decisions read; the projection path stays open.
