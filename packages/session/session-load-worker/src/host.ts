/**
 * Host side of one session page load. The worker owns decode + normalization;
 * the host settles on the single Result/Error message, worker death, or
 * cancellation.
 * @module @deepseek-ai/dsh-session-load-worker/host
 */

import { tmpdir } from 'node:os'
import { Worker } from 'node:worker_threads'
import type { WorkerOptions } from 'node:worker_threads'
import { fileURLToPath } from 'node:url'
import { HostToWorkerType, WorkerToHostType } from './protocol.ts'
import type { LoadRequest, LoadedPage, WorkerToHostMessage } from './protocol.ts'

/** Page size when the caller does not resolve one. */
export const DEFAULT_MAX_MESSAGES = 50

function renderThrown(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function assertNever(value: never, subject: string): never {
  throw new Error(`unexpected ${subject}: ${String(value)}`)
}

/**
 * The scrubbed worker environment: no ambient credentials, no loader flags.
 * Windows derives `os.tmpdir()` from `TMP`/`TEMP` and falls back to a
 * cwd-relative path when the environment is empty, so the host's real temp path
 * (not a credential) is injected there. The unbuilt shape additionally forwards
 * `TSX_TSCONFIG_PATH` for path resolution.
 * @param platform - host platform; overridable so tests exercise both peer arms.
 * @param tsconfigPath - the tsconfig pin to forward; only the unbuilt caller passes one.
 * @returns the scrubbed worker environment object.
 */
function workerSpawnEnv(platform: NodeJS.Platform = process.platform, tsconfigPath?: string): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = {}
  if (platform === 'win32') {
    const tmp = tmpdir()
    env.TMP = tmp
    env.TEMP = tmp
  }
  if (tsconfigPath !== undefined) env.TSX_TSCONFIG_PATH = tsconfigPath
  return env
}

/**
 * Resolve a built worker bundle or an unbuilt bootstrap that installs both tsx
 * transforms inside the worker. Both shapes clear `execArgv` and the ambient
 * environment.
 * @param request - the load payload, passed as `workerData`.
 * @returns the entry path or URL and the Worker options to spawn it with.
 */
function resolveWorkerSpawn(request: LoadRequest): { entry: string | URL; options: WorkerOptions } {
  /* v8 ignore next 3 -- the built-output arm: tests always run unbuilt (src/) */
  if (!import.meta.url.endsWith('.ts')) {
    return { entry: fileURLToPath(new URL('./worker.cjs', import.meta.url)), options: { workerData: request, env: workerSpawnEnv(), execArgv: [] } }
  }
  const workerEntry = new URL('./worker.ts', import.meta.url)
  const tsxEsmApiEntry = import.meta.resolve('tsx/esm/api')
  const tsxCjsApiEntry = import.meta.resolve('tsx/cjs/api')
  const bootstrap = [
    `import { register as registerEsm } from ${JSON.stringify(tsxEsmApiEntry)}`,
    `import { register as registerCjs } from ${JSON.stringify(tsxCjsApiEntry)}`,
    'registerCjs()',
    'registerEsm()',
    `await import(${JSON.stringify(workerEntry.href)})`,
  ].join('\n')
  return {
    entry: new URL(`data:text/javascript,${encodeURIComponent(bootstrap)}`),
    options: {
      workerData: request,
      env: workerSpawnEnv(undefined, process.env.TSX_TSCONFIG_PATH),
      execArgv: [],
    },
  }
}

/**
 * Load one bounded session-history page in a worker thread. Decode and
 * persistence normalization run inside the worker; the full decoded log stays
 * there and only the page crosses the boundary.
 * @param request - the log root, physical encoding, session id, and page window.
 * @param signal - optional cancellation; aborts the worker.
 * @returns the page (header, events, hasMore), rejecting on any read/decode failure.
 */
export function loadSessionPage(request: LoadRequest, signal?: AbortSignal): Promise<LoadedPage> {
  const { entry, options } = resolveWorkerSpawn(request)
  const worker = new Worker(entry, options)
  return new Promise<LoadedPage>((resolve, reject) => {
    let settled = false
    const onAbort = (): void => {
      settle(() => {
        void worker.terminate()
        reject(new Error('session load aborted'))
      })
    }
    const cleanup = (): void => {
      if (signal !== undefined) signal.removeEventListener('abort', onAbort)
    }
    const settle = (finish: () => void): void => {
      if (settled) return
      settled = true
      cleanup()
      finish()
    }
    worker.on('message', (message: WorkerToHostMessage) => {
      if (settled) return
      switch (message.type) {
        case WorkerToHostType.Ready:
          worker.postMessage({ type: HostToWorkerType.Go })
          break
        case WorkerToHostType.Log:
          // Diagnostics stay inside the worker; a host may forward them later.
          break
        case WorkerToHostType.Result:
          settle(() => {
            void worker.terminate()
            resolve(message.page)
          })
          break
        case WorkerToHostType.Error:
          settle(() => {
            void worker.terminate()
            reject(new Error(message.rendered))
          })
          break
        /* v8 ignore next 2 -- closed engine-owned union; the arm only makes adding a message type a compile error */
        default:
          assertNever(message, 'worker-to-host message')
      }
    })
    worker.on('error', (error) => {
      settle(() => reject(new Error(`session load worker failed: ${renderThrown(error)}`)))
    })
    worker.on('exit', (code) => {
      if (!settled) {
        settle(() => reject(new Error(`session load worker exited before settling (exit code ${code})`)))
      }
    })
    if (signal?.aborted) {
      onAbort()
    } else if (signal !== undefined) {
      signal.addEventListener('abort', onAbort, { once: true })
    }
  })
}
