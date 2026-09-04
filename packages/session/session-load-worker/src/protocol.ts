/**
 * The host⇄worker wire protocol: one enum of message tags per direction, a
 * payload map giving each tag its parameters, and the message unions derived
 * from them. Payloads are plain JSON by construction for structured clone.
 * @module @deepseek-ai/dsh-session-load-worker/protocol
 */

import type { SessionEvent, SessionHeader, SessionId } from '@deepseek-ai/dsh-session'
import type { JsonlCompression } from '@deepseek-ai/dsh-session-persistence-jsonl/format'

/** Message tags the worker sends the host (the wire values are the tag strings). */
export enum WorkerToHostType {
  /** The startup handshake: the worker is listening and awaits {@link HostToWorkerType.Go}. */
  Ready = 'ready',
  /** Diagnostics: how many events the worker decoded. */
  Log = 'log',
  /** The run's single terminal page. */
  Result = 'result',
  /** The run's rendered failure. */
  Error = 'error',
}

/** The payload each worker→host tag carries. */
export interface WorkerToHostPayloads {
  /** Ready carries nothing. */
  [WorkerToHostType.Ready]: Record<never, never>
  /** The diagnostic message, verbatim. */
  [WorkerToHostType.Log]: { message: string }
  /** The bounded page (header, events, hasMore). */
  [WorkerToHostType.Result]: { page: LoadedPage }
  /** The rendered decode/read failure. */
  [WorkerToHostType.Error]: { rendered: string }
}

/** Message tags the host sends the worker (the wire values are the tag strings). */
export enum HostToWorkerType {
  /** Releases the startup gate: run the load. */
  Go = 'go',
}

/** The payload each host→worker tag carries. */
export interface HostToWorkerPayloads {
  /** Go carries nothing. */
  [HostToWorkerType.Go]: Record<never, never>
}

/**
 * One worker→host message of tag `T`; unparameterized, the closed union over
 * every tag (a discriminated union — `switch` on `type` narrows).
 */
export type WorkerToHostMessage<T extends WorkerToHostType = WorkerToHostType> =
  { [K in T]: { type: K } & WorkerToHostPayloads[K] }[T]

/**
 * One host→worker message of tag `T`; unparameterized, the closed union over
 * every tag (a discriminated union — `switch` on `type` narrows).
 */
export type HostToWorkerMessage<T extends HostToWorkerType = HostToWorkerType> =
  { [K in T]: { type: K } & HostToWorkerPayloads[K] }[T]

/**
 * The worker's `workerData`: where and how to find the log plus the page window.
 * `beforeSeq` pages backwards from the window tail; `maxMessages` is the
 * append-origin message quota already resolved by the caller.
 */
export interface LoadRequest {
  /** The JSONL backend's session root directory. */
  root: string
  /** Physical artifact encoding. */
  compression: JsonlCompression
  /** The persisted session to load. */
  id: SessionId
  /** Exclusive lower bound: only events with a smaller seq enter the window. */
  beforeSeq?: number
  /** Append-origin message quota for one page. */
  maxMessages: number
}

/** One bounded history page returned by the worker. */
export interface LoadedPage {
  /** The stored session header parsed from the log's first line. */
  meta: SessionHeader
  /** The page's contiguous event range. */
  events: SessionEvent[]
  /** Whether older history precedes the page. */
  hasMore: boolean
}
