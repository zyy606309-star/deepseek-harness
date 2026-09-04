# Agent Note: Session-load-worker cold history

Status: implemented

English | [中文](2026-09-03-session-load-worker-cold-history.zh.md)

## Problem

A cold session-history read — a browser opening an old session without activating a Session or publishing an Agent — had to decode and normalize a complete JSONL log on the host just to serve one bounded page. The host retained the whole decoded event array in memory for the duration of the read, and every future consumer that wanted a bounded page would reimplement pagination and cold-read validation.

## Decision

`@deepseek-ai/dsh-session-load-worker` owns the cold page read as a library, not a Cordis plugin. `loadSessionPage(request, signal?)` spawns one `node:worker_threads` worker per call, passes the request as `workerData`, and settles on the single terminal page.

The worker resolves, reads, decodes, and normalizes the log with the JSONL backend's own cold-read primitives (`resolveLogPath`, `readStableFile`, `readPrefixBuffer` from `@deepseek-ai/dsh-session-persistence-jsonl/decode`) plus `snapshotStoredEvents` and `assertKnownEventTypes` from `@deepseek-ai/dsh-session-persistence`. The complete decoded event array stays in the worker; the only payloads that cross the message channel are the `ready` handshake, one `log` diagnostic line, and one `result` page or `error` rendering.

Pagination mirrors `dsh-host-apiproxy`'s `paginate`: count append-origin `user/message` and `assistant/message` events backwards from the window tail, pull each counted message's chunk group in through `sourceEventSeqs`, and cut at the oldest counted group's starting `seq`. One page is always a contiguous ascending `seq` range with `hasMore = cut > 0`; `beforeSeq` shifts the window tail backward.

The wire protocol is one enum of tags per direction (`ready` / `log` / `result` / `error` worker→host; `go` host→worker), with a `ready`→`go` release gate so the host signals its listeners before work starts. The host settles once on the first of the `result` page, the `error` rendering, worker `error`, worker `exit` before settling, or the abort signal, which terminates the worker. The worker spawns with a scrubbed environment — no ambient credentials, `execArgv: []` — forwarding only `TMP`/`TEMP` on Windows and `TSX_TSCONFIG_PATH` for the unbuilt bootstrap. The built entry is `./worker.cjs` (CommonJS, path-resolved); the unbuilt shape installs both tsx transforms through a data-URL bootstrap so source launch works without a prebuilt tree.

The invariant companion registers an empty installer: the package exposes no same-process event relation, and the worker protocol plus the built-worker path are its boundary.

## Alternatives considered

- **Keep cold reads fully in-process on the host (the current api-proxy path).** Rejected as the package's raison d'être: the whole decoded log stays in host memory for the read, which is the cost the worker boundary removes. api-proxy retains this path until the deferred wiring lands.
- **Stream decoded events from the worker and paginate on the host.** Rejected: it crosses the complete log across the channel, which reintroduces whole-log retention on the host side.
- **Stop decoding at the page cut.** Rejected: packed chunk rows reconstruct `seq`/`time` from the front of the log and torn-tail recovery reads to the end, so a bounded crossing without a full decode is not available on the JSONL format.

## Consequences

Only the JSONL backend is supported; there is no SQLite or query-service read path. api-proxy wiring is deferred: the gateway still reads cold history through its own in-process path and does not call `loadSessionPage`, so two pagination implementations coexist and stay aligned by review until adoption.

Every load still scans the complete log — the worker reads and decodes the whole artifact to find the window, then posts only the page. The boundary bounds bytes returned per page, not bytes read or decoded, so a very large log still pays its full decode cost per cold page read. The worker's normalized log is discarded with the worker; nothing is cached across calls, which keeps each read a clean, disposable decode but re-pays startup and decode for every page.

Tests drive the unbuilt tsx bootstrap and the direct worker source, and pin the page window against the full log, `hasMore`, `beforeSeq`, Zstandard and raw compression, and the bounded crossing (`JSON.stringify(page)` never carries older turns' text).
