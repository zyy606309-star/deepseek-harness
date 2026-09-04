# @deepseek-ai/dsh-session-load-worker

English | [中文](README.zh.md)

Worker-thread cold loader for bounded session-history pages. JSONL decode and persistence normalization run inside a `node:worker_threads` worker; the full decoded log stays in the worker and only one bounded page crosses back to the host. The package is not a Cordis plugin and contributes no live session service — it is a library entry (`loadSessionPage`) a host-side consumer calls to read a stored log without activating a Session or publishing an Agent.

## Purpose

`loadSessionPage` reads one persisted JSONL session log and returns a bounded history page. It exists so a cold history read (for example a browser opening an old session) pays decode, validation, and normalization inside a disposable worker and retains no whole-log copy in the host's memory. The package owns only the cold page read: it never resumes the session, never appends to the log, and never assembles or sends a model request.

## Public API

`src/index.ts` exports `loadSessionPage`, `DEFAULT_MAX_MESSAGES`, and the `LoadedPage` / `LoadRequest` types.

- `loadSessionPage(request, signal?): Promise<LoadedPage>` — spawns one worker per call, sends the request as `workerData`, and resolves with the single terminal page. `request` is `{ root, compression, id, beforeSeq?, maxMessages }`; `signal` is an optional `AbortSignal` that terminates the worker.
- `DEFAULT_MAX_MESSAGES = 50` — the page quota used when a caller does not resolve one.
- `LoadedPage` — `{ meta: SessionHeader, events: SessionEvent[], hasMore: boolean }`: the stored header, one contiguous raw event range, and whether older history precedes the page.
- `LoadRequest` — `root` (the JSONL backend's session root), `compression` (`'zstd' | 'none'`), `id` (`SessionId`), `beforeSeq?` (exclusive lower bound: only events with a smaller `seq` enter the window; absent selects the full tail), and `maxMessages` (append-origin message quota).

There is no default export and no Cordis service. The sibling `./invariant` companion (`src/invariant.ts`) registers an empty installer whose reason documents that the worker protocol and the built-worker path are this package's only boundary.

## Bounded-page guarantee

One page is always a contiguous, ascending `seq` range, never a message fragment. `maxMessages` counts append-origin `user/message` and `assistant/message` events backwards from the window tail; each counted message pulls its chunk group in via `sourceEventSeqs`, so the cut lands on the oldest counted message group's starting `seq`. `hasMore` is true exactly when `cut > 0` (older history precedes the page), and `beforeSeq` shifts the window tail backward for older pages. `meta` always carries the log's stored `SessionHeader` regardless of the window.

The pagination rule mirrors `dsh-host-apiproxy`'s `paginate` so that, once wired, a page served through this worker matches the host gateway's page boundaries.

## Worker boundary

The worker resolves, reads, decodes, and normalizes the log with the JSONL backend's own cold-read primitives (`resolveLogPath`, `readStableFile`, `readPrefixBuffer` from `@deepseek-ai/dsh-session-persistence-jsonl/decode`), then applies `snapshotStoredEvents` and `assertKnownEventTypes` from `@deepseek-ai/dsh-session-persistence`. The complete decoded event array stays in the worker; the only payloads that cross are the startup `ready` handshake, one `log` diagnostic line, and the single `result` page or `error` rendering.

The host settles on the first of: the `result` page, the `error` rendering, worker `error`, worker `exit` before settling, or the abort signal. The worker spawns with a scrubbed environment — no ambient credentials, `execArgv: []` — and forwards only `TMP`/`TEMP` (Windows) and, for the unbuilt bootstrap, `TSX_TSCONFIG_PATH`. The built entry is `./worker.cjs` (CommonJS, path-resolved); the unbuilt shape installs both tsx transforms through a data-URL bootstrap so source launch works without a prebuilt tree.

## Cancellation and errors

- `signal` aborts the worker (`worker.terminate()`) and rejects with `session load aborted`; an already-aborted signal rejects immediately.
- A missing artifact rejects with `session "<id>" has no stored JSONL artifact`.
- A decode or validation failure rejects with the worker's rendered message.
- A worker that fails or exits without settling rejects with `session load worker failed: …` or `session load worker exited before settling (exit code N)`.

Rejection and resolution settle exactly once; the settle guard makes a later message, exit, or abort a no-op after the first.

## Model Experience

None, as this package decodes and pages a stored session log for client-facing history reads and touches no prompt, message, schema, stream, or tool result.

#### KV Cache effect

None; the worker neither assembles nor sends a provider request, and its host-side consumer reads history for a browser rather than a model.

## Known Limitations and Deferred Work

- **Only the JSONL backend is supported** — `loadSessionPage` resolves, reads, and decodes a `session-persistence-jsonl` artifact only; there is no SQLite or query-service read path, so a deployment whose sessions live in another backend cannot page through this worker.
- **api-proxy wiring is not yet connected** — `dsh-host-apiproxy` still reads cold history through its own in-process path and does not call `loadSessionPage`; this package is a standalone library until the gateway adopts it, and the two pagination implementations must stay aligned by review until then.
- **Every load still scans the complete log** — the worker reads and decodes the whole artifact to find the window, then posts only the page, so the crossing is bounded but the read and decode cost is not; it is bounded per page in bytes returned, not in bytes read.
