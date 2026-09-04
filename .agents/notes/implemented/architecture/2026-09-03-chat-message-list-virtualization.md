# Agent Note: Windowed long-transcript chat rendering

Status: implemented

English | [中文](2026-09-03-chat-message-list-virtualization.zh.md)

## Problem

The chat transcript renders every keyed business node through `ChatView`'s `order.map`, so a long session mounts one live, independently-subscribing `ChatNodeSeat` per user, assistant, and tool node. Node count grows without bound as a session runs, and each seat is a live `useSession` subscription plus a keyed slot dispatch that can recurse into a tool-call tree. A multi-page transcript therefore holds thousands of rows in the DOM at once, and opening or scrolling it becomes slow even though the host-side message derivation (`Session.deriveMessages`) and the surface fold are already incremental. The trajectory ledger had the same problem and solved it with `@tanstack/react-virtual`; the chat flow had only a CSS comment reserving `.flowItem` as the future mount unit.

## Decision

`ChatView` windows the keyed-node list with `@tanstack/react-virtual` v3 above a `VIRTUALIZATION_THRESHOLD = 100` node count. At or above the threshold the rendered list is a `.virtualWindow` whose items are absolutely positioned `ChatNodeSeat` rows; below it the original plain `order.map` flow is unchanged, so every existing anchor, rail, and scroll contract keeps reading the fully mounted set for the overwhelmingly common short transcript.

The window is one flex child of the existing message column, so the 16 px column gap still separates it from the load-older row and the tail chrome, and item spacing is owned by the virtualizer's `gap: 16` rather than by the column gap (the two never stack). Item heights are variable: `estimateSize: 200` seeds the measurement and `measureElement` corrects each item once the browser observes it. `overscan: 12`, `initialRect` height 600 (a non-empty first frame and a jsdom-testable window), and `paddingEnd: 16` close the tail gap.

The virtual window is a mid-column child, not the scrollport's content top, so a `useLayoutEffect` measures its offset from the resolved scrollport and feeds it as `scrollMargin`, keeping item starts and the range scrollport-relative while the open-state hint and the load-older row sit above it. A `ResizeObserver` re-measures when those siblings or the viewport resize.

The scrollport is resolved by the existing `scrollerOf`: the ancestor `[data-conversation-scroll]` in production, the view-local `.scroll` when the view is mounted alone in tests. Rail marker positions and `jumpToUser` switch to index-based math under windowing (`scrollToIndex`), because the target row may be unmounted; the non-windowed path keeps its DOM-anchor math.

Stream rendering cadence is unchanged by this decision: the assistant definition already publishes visible chunks at `animation-frame` and the `Notifier.markFrameDirty` collapses them to one flush per frame, so windowing only bounds the mount set, not the streaming cadence.

## Alternatives considered

**Always-on windowing.** Rejected: a threshold keeps the short-transcript path byte-identical to the proven legacy flow, so the existing scroll/anchor/rail contract and its tests hold without a full rewrite, and the windowed branch only activates where the mount cost is real.

**Hand-rolled window instead of `@tanstack/react-virtual`.** Rejected: the dependency is already in the workspace (the trajectory ledger uses v3.14.9), it owns ResizeObserver measurement, scroll reconciliation, and index alignment, and reusing it keeps the two windowed surfaces on one measured implementation.

**Fixed-height rows.** Rejected: chat rows hold variable markdown, tool cards, and images, so a fixed estimate without `measureElement` would misplace the scroll position as items reveal their true height.

## Consequences

- Long-transcript mount cost is bounded by viewport plus overscan instead of by total node count, removing the dominant open/scroll cost without touching the host-side incremental derivation.
- Rail and jump navigation now carry index-based positioning for the windowed branch in addition to the DOM-anchor path for short transcripts; both are covered by the existing `chat-view.client.spec.tsx` suite plus a windowing case that asserts the mounted node count stays below the total.
- The browser e2e scroll contract stays virtualizer-neutral: its DOM-cardinality probe was replaced with a scrollport `scrollHeight` probe, so paging/streaming assertions measure content growth rather than mounted rows.
