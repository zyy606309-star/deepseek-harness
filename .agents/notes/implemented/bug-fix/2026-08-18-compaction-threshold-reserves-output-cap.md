# Agent Note: compaction pressure reserves the model's output cap

Status: implemented

English | [中文](2026-08-18-compaction-threshold-reserves-output-cap.zh.md)

## Problem

`compaction-basic` priced its pressure threshold against the model's full combined context window (`floor(contextWindow × thresholdRatio)`), ignoring that every conversation request also declares an output budget (`max_tokens`, default 256,000 on the DeepSeek adapter). A provider's context window is the combined input-plus-output limit, so the history can only occupy `contextWindow − max_tokens` before the next request — the replayed history plus the reserved output — exceeds the window.

With the shipped defaults — a 1,000,000 window, a 256,000 output cap, and a `0.8` threshold — compaction waited until 800,000 tokens while the effective input budget was 744,000. A conversation therefore overflowed in the 744K–800K band before compaction could fire. The provider closed the SSE stream without `[DONE]`, surfacing `STREAM_CLOSED`, which is neither `CONTEXT_WINDOW_EXCEEDED` (so the overflow-recovery path ignored it) nor in the default retryable set (so `dsh-llm-retry` did not retry) — a terminal turn failure.

## Decision

`resolveCompactSpec` now accepts the adapter's per-request output cap (`defaultMaxTokens` from `resolveModelInfo`) and prices the pressure threshold against the effective input budget: `floor((contextWindow − outputCap) × thresholdRatio)`. Retention still prices the full window, because the retained tail expresses how much recent history to keep verbatim, not output room. An omitted, non-integer, non-positive, or at-or-above-window cap falls back to the full window, preserving the previous behavior for adapters that report no cap.

With the shipped defaults the threshold becomes `floor(744,000 × 0.8) = 595,200`, so compaction fires while the conversation still has room for the reserved output.

## Alternatives considered

**Lower the default `thresholdRatio` (0.8 → 0.6).** Fixes the shipped default but leaves the same defect for any model whose output cap is a different fraction of its window, and silently re-means a value deployments configured against the full window. Rejected in favor of pricing the reserve directly.

**Reserve an estimated output instead of the adapter's full `max_tokens`.** A conversation step usually emits far less than the cap, so reserving the cap is conservative and compacts earlier than strictly necessary. Rejected because the provider checks the request's declared `max_tokens` against the combined window, not the eventual output; reserving less would still let a request exceed the window.

**Treat `STREAM_CLOSED` as a compaction trigger or a retryable failure.** The DeepSeek adapter deliberately classifies a clean partial EOF as non-retryable `STREAM_CLOSED` (a truncated response has no trustworthy finish), and retrying the same oversized request would not help. The overflow-recovery path already handles a clean provider `CONTEXT_WINDOW_EXCEEDED`. Rejected; the fix is to avoid reaching the point where the provider truncates.

## Consequences

Compaction now triggers earlier on any model that reports a per-request output cap — with the shipped DeepSeek defaults, at ~595K instead of ~800K. A deployment whose provider does not reserve `max_tokens` against the combined window keeps the old timing by omitting the cap from its adapter. `ResolvedCompactSpec.contextWindow` still reports the full window while `thresholdTokens` reflects the reserved budget, so readers that only compared `thresholdTokens` against occupancy are unaffected.

## Testing

`packages/compaction/compaction-basic/tests/compaction-basic.spec.ts` — `resolveCompactSpec` prices the threshold against `contextWindow − outputCap` and falls back to the full window for omitted, non-integer, non-positive, and at-or-above-window caps; an integration case proves `compactIfNeeded` reads `defaultMaxTokens` from `resolveModelInfo` and compacts a fixture that stays below the unreserved threshold.
