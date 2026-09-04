/**
 * Tests for the worker-thread cold loader: `loadSessionPage` pages a JSONL
 * session log inside a worker and crosses only the bounded page back to the
 * host. Fixtures reuse the JSONL persistence backend (mounted through Cordis)
 * to produce on-disk logs, exactly like the JSONL suite, then load them
 * through the worker and assert the page window — never the full decoded log.
 * @module @deepseek-ai/dsh-session-load-worker/tests/worker
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { Worker } from 'node:worker_threads'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { Context } from '@deepseek-ai/cordis'
import { createMessage, createUserMessage } from '@deepseek-ai/dsh-llm'
import SessionStore, { SessionId } from '@deepseek-ai/dsh-session'
import type { SessionEvent, SessionHeader } from '@deepseek-ai/dsh-session'
import JsonlSessionPersistence from '@deepseek-ai/dsh-session-persistence-jsonl'
import type { JsonlCompression } from '@deepseek-ai/dsh-session-persistence-jsonl/format'
import { loadSessionPage } from '../src/index.ts'
import { HostToWorkerType, WorkerToHostType } from '../src/protocol.ts'
import type { LoadRequest, LoadedPage, WorkerToHostMessage } from '../src/protocol.ts'

// Cold worker startup can be slow on contended Windows/CI runners.
vi.setConfig({ testTimeout: 30_000 })

const roots: string[] = []
const contexts: Context[] = []

async function freshRoot(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), 'dsh-load-worker-'))
  roots.push(root)
  return root
}

/** Mount the JSONL backend over a fresh root; reused from the JSONL suite's own wiring. */
async function mount(root: string, compression: JsonlCompression): Promise<Context> {
  const ctx = new Context()
  contexts.push(ctx)
  await ctx.plugin(SessionStore)
  await ctx.plugin(JsonlSessionPersistence, { root, compression })
  return ctx
}

afterEach(async () => {
  for (const ctx of contexts.splice(0).reverse()) await ctx.fiber.dispose()
  for (const root of roots.splice(0)) await rm(root, { recursive: true, force: true })
})

/**
 * Append a user/message surface event (no source chunks), then an assistant
 * turn whose message cites two `assistant/chunk` seqs. Seqs are `events.length`,
 * so the log is contiguous from 0 by construction.
 */
function appendUser(events: SessionEvent[], text: string): void {
  events.push({
    type: 'user/message',
    seq: events.length,
    time: events.length + 1,
    data: createUserMessage({ content: [{ type: 'text', text }], source: { kind: 'user' } }),
    surfaceOp: 'append',
  })
}

/** Append a closed turn: chunk stream (2 deltas) + citing assistant/message. */
function appendAssistantTurn(events: SessionEvent[], turn: number, text: string): void {
  const chunkSeqs: number[] = []
  events.push({ type: 'turn/start', seq: events.length, time: events.length + 1, data: { turn } })
  events.push({ type: 'step/start', seq: events.length, time: events.length + 1, data: { turn, step: 1 } })
  for (const piece of [text.slice(0, 1), text.slice(1)]) {
    chunkSeqs.push(events.length)
    events.push({
      type: 'assistant/chunk',
      seq: events.length,
      time: events.length + 1,
      data: { turn, step: 1, chunk: { type: 'text-delta', index: 0, text: piece } },
    })
  }
  events.push({
    type: 'assistant/message',
    seq: events.length,
    time: events.length + 1,
    data: {
      turn,
      step: 1,
      message: createMessage({
        role: 'assistant',
        content: [{ type: 'text', text }],
        source: { kind: 'model', provider: 'mock', model: 'mock' },
      }),
    },
    surfaceOp: 'append',
    sourceEventSeqs: chunkSeqs,
  })
  events.push({ type: 'step/end', seq: events.length, time: events.length + 1, data: { turn, step: 1 } })
  events.push({ type: 'turn/end', seq: events.length, time: events.length + 1, data: { turn, reason: { kind: 'completed' } } })
}

/**
 * Three closed turns, 24 events (seqs 0..23). Turn 3 occupies seqs 16..23:
 * user/message(16), turn/start(17), step/start(18), chunk(19), chunk(20),
 * assistant/message(21), step/end(22), turn/end(23). Six append-origin
 * messages total (user + assistant per turn).
 */
function threeTurnLog(): SessionEvent[] {
  const events: SessionEvent[] = []
  for (let turn = 1; turn <= 3; turn++) {
    appendUser(events, `question ${turn}`)
    appendAssistantTurn(events, turn, `answer ${turn}`)
  }
  return events
}

/** Write one log through the backend and return its live context. */
async function seedLog(
  root: string,
  compression: JsonlCompression,
  id: string,
  cwd: string,
  events: SessionEvent[],
): Promise<Context> {
  const ctx = await mount(root, compression)
  const header: SessionHeader = { version: 0, id: SessionId(id), createdAt: 1000, cwd, delegationDepth: 0 }
  await ctx.sessionPersistence.create(header)
  await ctx.sessionPersistence.append(SessionId(id), events)
  return ctx
}

/** Spawn the worker source directly (tsx bootstrap), mirroring the host's own unbuilt spawn. */
function runWorkerSource(request: LoadRequest): Promise<LoadedPage> {
  const workerEntry = new URL('../src/worker.ts', import.meta.url)
  const bootstrap = [
    `import { register as registerEsm } from ${JSON.stringify(import.meta.resolve('tsx/esm/api'))}`,
    `import { register as registerCjs } from ${JSON.stringify(import.meta.resolve('tsx/cjs/api'))}`,
    'registerCjs()',
    'registerEsm()',
    `await import(${JSON.stringify(workerEntry.href)})`,
  ].join('\n')
  const env: NodeJS.ProcessEnv = {}
  if (process.platform === 'win32') {
    env.TMP = tmpdir()
    env.TEMP = tmpdir()
  }
  if (process.env.TSX_TSCONFIG_PATH !== undefined) env.TSX_TSCONFIG_PATH = process.env.TSX_TSCONFIG_PATH
  return new Promise<LoadedPage>((resolve, reject) => {
    const worker = new Worker(new URL(`data:text/javascript,${encodeURIComponent(bootstrap)}`), {
      workerData: request,
      env,
      execArgv: [],
    })
    let settled = false
    worker.on('message', (message: WorkerToHostMessage) => {
      if (settled) return
      switch (message.type) {
        case WorkerToHostType.Ready:
          worker.postMessage({ type: HostToWorkerType.Go })
          break
        case WorkerToHostType.Log:
          break
        case WorkerToHostType.Result:
          settled = true
          void worker.terminate()
          resolve(message.page)
          break
        case WorkerToHostType.Error:
          settled = true
          void worker.terminate()
          reject(new Error(message.rendered))
          break
      }
    })
    worker.on('error', (error) => {
      settled = true
      reject(new Error(`session load worker failed: ${error instanceof Error ? error.message : String(error)}`))
    })
    worker.on('exit', (code) => {
      if (!settled) reject(new Error(`session load worker exited before settling (exit code ${code})`))
    })
  })
}

describe('session-load-worker', () => {
  describe('loadSessionPage over the JSONL backend', () => {
    it('returns a bounded page with maxMessages=1 and reports hasMore', async () => {
      const root = await freshRoot()
      const ctx = await seedLog(root, 'none', 'bounded', '/work', threeTurnLog())
      const full = (await ctx.sessionPersistence.load(SessionId('bounded'))).events

      const page = await loadSessionPage({ root, compression: 'none', id: SessionId('bounded'), maxMessages: 1 })

      expect(page.meta.id).toBe(SessionId('bounded'))
      // One append-origin message (turn 3's assistant/message) pulls its chunk
      // group in via sourceEventSeqs — never cut mid-message.
      expect(page.events.map(e => e.seq)).toEqual([19, 20, 21, 22, 23])
      expect(page.events.length).toBeLessThan(full.length)
      expect(page.hasMore).toBe(true)
    })

    it('crosses only the bounded page, never the complete decoded log', async () => {
      const root = await freshRoot()
      const ctx = await seedLog(root, 'none', 'no-full-events', '/work', threeTurnLog())
      const full = (await ctx.sessionPersistence.load(SessionId('no-full-events'))).events

      const page = await loadSessionPage({ root, compression: 'none', id: SessionId('no-full-events'), maxMessages: 1 })

      // The page is a strict, contiguous tail suffix of the full log.
      expect(full.map(e => e.seq)).toEqual(Array.from({ length: 24 }, (_, i) => i))
      expect(page.events.length).toBeLessThan(full.length)
      expect(page.events.map(e => e.seq)).toEqual(full.slice(19).map(e => e.seq))
      // Older turns' text never crosses the boundary.
      expect(JSON.stringify(page)).not.toContain('question 1')
      expect(JSON.stringify(page)).not.toContain('answer 1')
      expect(JSON.stringify(page)).toContain('answer 3')
    })

    it('counts append-origin messages: larger quotas widen the page and clear hasMore', async () => {
      const root = await freshRoot()
      const ctx = await seedLog(root, 'none', 'quota', '/work', threeTurnLog())
      const id = SessionId('quota')

      const two = await loadSessionPage({ root, compression: 'none', id, maxMessages: 2 })
      expect(two.events.map(e => e.seq)).toEqual([16, 17, 18, 19, 20, 21, 22, 23])
      expect(two.hasMore).toBe(true)

      // Six messages exactly fills the whole log: no older history remains.
      const six = await loadSessionPage({ root, compression: 'none', id, maxMessages: 6 })
      expect(six.events.length).toBe(24)
      expect(six.hasMore).toBe(false)

      const over = await loadSessionPage({ root, compression: 'none', id, maxMessages: 100 })
      expect(over.events.length).toBe(24)
      expect(over.hasMore).toBe(false)

      await ctx.fiber.dispose()
    })

    it('pages backward from beforeSeq', async () => {
      const root = await freshRoot()
      const ctx = await seedLog(root, 'none', 'before-seq', '/work', threeTurnLog())
      const id = SessionId('before-seq')

      // beforeSeq excludes turn 3's assistant/message (seq 21) and later; the
      // window tail is then turn 3's user/message group (seq 16..20).
      const page = await loadSessionPage({ root, compression: 'none', id, beforeSeq: 21, maxMessages: 1 })

      expect(page.events.map(e => e.seq)).toEqual([16, 17, 18, 19, 20])
      expect(page.hasMore).toBe(true)

      await ctx.fiber.dispose()
    })

    it('loads a Zstandard-compressed log through the worker', async () => {
      const root = await freshRoot()
      const ctx = await seedLog(root, 'zstd', 'zstd-log', '/work', threeTurnLog())
      const id = SessionId('zstd-log')

      const page = await loadSessionPage({ root, compression: 'zstd', id, maxMessages: 1 })

      expect(page.meta.id).toBe(id)
      expect(page.events.map(e => e.seq)).toEqual([19, 20, 21, 22, 23])
      expect(page.hasMore).toBe(true)

      await ctx.fiber.dispose()
    })
  })

  describe('worker source', () => {
    it('starts directly and serves a bounded Result through the Ready→Go handshake', async () => {
      const root = await freshRoot()
      const ctx = await seedLog(root, 'none', 'direct-worker', '/work', threeTurnLog())

      const page = await runWorkerSource({
        root,
        compression: 'none',
        id: SessionId('direct-worker'),
        maxMessages: 1,
      })

      expect(page.meta.id).toBe(SessionId('direct-worker'))
      expect(page.events.map(e => e.seq)).toEqual([19, 20, 21, 22, 23])
      expect(page.hasMore).toBe(true)

      await ctx.fiber.dispose()
    })
  })
})
