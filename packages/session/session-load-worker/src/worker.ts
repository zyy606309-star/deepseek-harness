/**
 * Worker entry: decodes the JSONL log, normalizes the stored events, and posts
 * only the bounded page. The full decoded log stays inside the worker.
 * @module @deepseek-ai/dsh-session-load-worker/worker
 */

import { parentPort, workerData } from 'node:worker_threads'
import type { MessagePort } from 'node:worker_threads'
import {
  adoptSessionEvent,
  foldSurface,
  interruptedTurnClosers,
  isAppendSurfaceEvent,
} from '@deepseek-ai/dsh-session'
import type { SessionEvent } from '@deepseek-ai/dsh-session'
import { adoptStoredEvents, assertKnownEventTypes } from '@deepseek-ai/dsh-session-persistence'
import {
  readPrefixBuffer,
  readStableFile,
  resolveLogPath,
} from '@deepseek-ai/dsh-session-persistence-jsonl/decode'
import { HostToWorkerType, WorkerToHostType } from './protocol.ts'
import type { HostToWorkerMessage, LoadRequest, LoadedPage } from './protocol.ts'

/** Conversation message event types (the pagination counting unit). */
const MESSAGE_TYPES = new Set(['user/message', 'assistant/message'])

function requireParentPort(port: MessagePort | null): MessagePort {
  if (port === null) throw new Error('session load worker must run on a worker thread')
  return port
}

function renderThrown(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

/**
 * Message-boundary pagination, mirroring api-proxy's `paginate`: count
 * maxMessages append-origin messages backwards from the window tail and cut at
 * the oldest message group's starting seq (chunks group via sourceEventSeqs —
 * never cut mid-message).
 * @param events - the normalized event log.
 * @param beforeSeq - exclusive lower bound; undefined selects the full tail.
 * @param maxMessages - append-origin message quota.
 * @returns the page and whether older history precedes it.
 */
function paginate(
  events: readonly SessionEvent[],
  beforeSeq: number | undefined,
  maxMessages: number,
): { events: SessionEvent[]; hasMore: boolean } {
  const window = beforeSeq === undefined ? [...events] : events.filter(event => event.seq < beforeSeq)
  let count = 0
  let cut = 0
  for (let i = window.length - 1; i >= 0; i--) {
    const event = window[i] as SessionEvent
    if (!MESSAGE_TYPES.has(event.type) || !isAppendSurfaceEvent(event)) continue
    count++
    let groupStart = event.seq
    for (const source of event.sourceEventSeqs ?? []) {
      if (source < groupStart) groupStart = source
    }
    if (count >= maxMessages) {
      cut = groupStart
      break
    }
  }
  return { events: window.filter(event => event.seq >= cut), hasMore: cut > 0 }
}

/** Resolve, read, decode, normalize, and page one session log; posts the page or the failure. */
async function load(port: MessagePort, request: LoadRequest): Promise<void> {
  try {
    const path = await resolveLogPath(request.root, request.compression, request.id)
    if (path === undefined) {
      throw new Error(`session "${request.id}" has no stored JSONL artifact`)
    }
    const { buffer } = await readStableFile(path)
    const decoded = await readPrefixBuffer(buffer, request.compression)
    const storedEvents = adoptStoredEvents(decoded.events, request.id)
    assertKnownEventTypes(storedEvents, request.id, { kind: 'jsonl', path })
    const closers = interruptedTurnClosers(storedEvents).map(adoptSessionEvent)
    const balanced = [...storedEvents, ...closers]
    foldSurface(balanced)
    const page = paginate(balanced, request.beforeSeq, request.maxMessages)
    const result: LoadedPage = { meta: decoded.meta, events: page.events, hasMore: page.hasMore }
    port.postMessage({ type: WorkerToHostType.Log, message: `loaded ${balanced.length} events from ${path}` })
    port.postMessage({ type: WorkerToHostType.Result, page: result })
  } catch (error) {
    port.postMessage({ type: WorkerToHostType.Error, rendered: renderThrown(error) })
  }
}

function run(port: MessagePort, request: LoadRequest): void {
  port.on('message', (message: HostToWorkerMessage) => {
    if (message.type === HostToWorkerType.Go) void load(port, request)
  })
  port.postMessage({ type: WorkerToHostType.Ready })
}

// workerData is `any` at the node:worker_threads boundary; the host is the
// only spawner and always provides a LoadRequest.
void run(requireParentPort(parentPort), workerData as LoadRequest)
