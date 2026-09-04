/**
 * Cold-read primitives for the JSONL session-persistence backend, exported so
 * the worker-thread cold loader resolves, reads, and decodes a session log
 * with the exact same revision-stable read, header-frame validation, and
 * torn-tail recovery the backend itself uses. Every function is pure with
 * respect to backend state: inputs are passed in, no class instance is read.
 * @module dsh-session-persistence-jsonl/decode
 */

import { open, readFile, readdir, stat } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { performance } from 'node:perf_hooks'
import { scheduler } from 'node:timers/promises'
import { SessionPersistenceRevision } from '@deepseek-ai/dsh-session-persistence'
import type { SessionPersistenceRevision as Revision } from '@deepseek-ai/dsh-session-persistence'
import type { SessionEvent, SessionHeader, SessionId } from '@deepseek-ai/dsh-session'
import { encodeSegment, logSuffix, scanLog, SessionLogScanner } from './format.ts'
import type { JsonlCompression } from './format.ts'
import { createZstdFrameDecoder, decompressZstdPrefix, scanZstdFrames } from './zstd.ts'

/**
 * Internal scheduling constant, not deployment configuration: balance
 * frame-boundary event-loop yields against `setImmediate` overhead. One frame
 * remains an indivisible synchronous decode.
 */
export const ZSTD_DECODE_YIELD_INTERVAL_MS = 500

interface FileRevisionIdentity {
  readonly dev: bigint
  readonly ino: bigint
  readonly size: bigint
  readonly mtimeNs: bigint
  readonly ctimeNs: bigint
}

/** Build the source-qualified revision shared by full and lightweight reads. */
export function fileRevision(identity: FileRevisionIdentity): Revision {
  return SessionPersistenceRevision([
    identity.dev,
    identity.ino,
    identity.size,
    identity.mtimeNs,
    identity.ctimeNs,
  ].join(':'))
}

/** Whether a filesystem error means absence; every non-ENOENT failure must surface. */
export function isENOENT(error: unknown): boolean {
  return (error as NodeJS.ErrnoException | null)?.code === 'ENOENT'
}

/**
 * Read a file's bytes under a revision-stable loop: a writer appending
 * between stat and readFile would yield a torn physical file, so retry
 * while the stat revision changes.
 * @param path - the artifact file to read.
 * @param signal - optional cancellation for the stat/read work.
 * @returns the stable bytes and the revision that matched both stats.
 */
export async function readStableFile(
  path: string,
  signal?: AbortSignal,
): Promise<{ buffer: Buffer; revision: Revision }> {
  for (;;) {
    signal?.throwIfAborted()
    const before = fileRevision(await stat(path, { bigint: true }))
    const buffer = await readFile(path, { signal })
    signal?.throwIfAborted()
    const after = fileRevision(await stat(path, { bigint: true }))
    if (before === after) return { buffer, revision: after }
  }
}

/** Assert that the independently decodable first frame contains only the header record. */
export function assertZstdHeaderFrame(plaintext: Buffer): void {
  if (plaintext.length === 0 || plaintext.indexOf(0x0A) !== plaintext.length - 1) {
    throw new Error('corrupt Zstandard session log: first frame is not exactly one header line')
  }
}

// --- artifact discovery (locate-only, no event decode) ---

/** The physical encoding this backend would pair against one selected mode. */
export function oppositeCompression(compression: JsonlCompression): JsonlCompression {
  return compression === 'zstd' ? 'none' : 'zstd'
}

/** Build the mixed-encoding refusal for one resolved artifact path. */
export function encodingMismatch(path: string, compression: JsonlCompression): Error {
  return new Error(
    `session artifact ${JSON.stringify(path)} uses ${logSuffix(oppositeCompression(compression))}, `
    + `but this backend is configured for compression ${JSON.stringify(compression)}; `
    + 'use a separate root or select the matching compression mode',
  )
}

/** Build the obsolete flat-file layout refusal for one resolved artifact path. */
export function legacyLayout(path: string): Error {
  return new Error(
    `session artifact ${JSON.stringify(path)} uses the unsupported flat-file layout; `
    + 'use a separate root or move it into a project/session directory before loading',
  )
}

/** Whether one artifact path exists; a blocked parent surfaces as a storage fault, never false absence. */
export async function exists(path: string): Promise<boolean> {
  try {
    const handle = await open(path, 'r')
    await handle.close()
    return true
  } catch (error) {
    // Only ENOENT means absent. A permission/I/O error must surface rather
    // than letting load or collision checks proceed under false absence.
    // Windows reports ENOENT, not ENOTDIR, for `regular-file/child`; verify
    // the immediate parent so a blocked session directory remains a storage fault.
    /* v8 ignore else -- Windows reports file-valued parents as ENOENT; POSIX covers direct ENOTDIR. */
    if (isENOENT(error)) {
      await assertLogParentAllowsAbsence(path)
      return false
    }
    /* v8 ignore next -- Windows repairs ENOTDIR from ENOENT above; POSIX covers direct ENOTDIR. */
    throw error
  }
}

/* v8 ignore start -- native Windows coverage exercises this repair; POSIX open reports ENOTDIR before this point. */
/** Distinguish a genuinely absent path from one blocked by a file-valued parent. */
async function assertLogParentAllowsAbsence(path: string): Promise<void> {
  try {
    const parent = dirname(path)
    const info = await stat(parent)
    if (info.isDirectory()) return
    const error = new Error(`ENOTDIR: parent path exists but is not a directory: ${parent}`) as NodeJS.ErrnoException
    error.code = 'ENOTDIR'
    error.path = parent
    throw error
  } catch (error) {
    if (isENOENT(error)) return
    throw error
  }
}
/* v8 ignore stop */

/** The human-readable project directories under a configured root. */
export async function listProjectDirs(root: string, signal?: AbortSignal): Promise<string[]> {
  try {
    signal?.throwIfAborted()
    const entries = await readdir(root, { withFileTypes: true })
    signal?.throwIfAborted()
    return entries.filter(e => e.isDirectory()).map(e => join(root, e.name))
  } catch (error) {
    // Only an absent root means no sessions; rethrow every other I/O failure.
    if (isENOENT(error)) return []
    throw error
  }
}

/** Reject the obsolete flat-file layout for one id before accepting a project directory. */
async function rejectLegacyFlatArtifact(
  project: string,
  id: SessionId,
  signal?: AbortSignal,
): Promise<void> {
  signal?.throwIfAborted()
  const encoded = encodeSegment(id)
  for (const compression of ['zstd', 'none'] as const) {
    const path = join(project, encoded + logSuffix(compression))
    const artifactExists = await exists(path)
    signal?.throwIfAborted()
    if (artifactExists) throw legacyLayout(path)
  }
}

/**
 * Resolve the unique physical log for an id across every project directory,
 * without reading or decoding it. Mirrors the backend's `findLog` discovery
 * (legacy-flat and mixed-encoding rejection included) so a worker resolves the
 * exact path the coordinator would have read.
 * @param root - the backend's session root directory.
 * @param compression - configured physical encoding.
 * @param id - the persisted session to locate.
 * @param signal - optional cancellation for the directory scan.
 * @returns the absolute log path, or `undefined` when no project owns the id.
 */
export async function resolveLogPath(
  root: string,
  compression: JsonlCompression,
  id: SessionId,
  signal?: AbortSignal,
): Promise<string | undefined> {
  const matches: string[] = []
  for (const project of await listProjectDirs(root, signal)) {
    signal?.throwIfAborted()
    await rejectLegacyFlatArtifact(project, id, signal)
    signal?.throwIfAborted()
    const dir = join(project, encodeSegment(id))
    const path = join(dir, `session${logSuffix(compression)}`)
    const opposite = join(dir, `session${logSuffix(oppositeCompression(compression))}`)
    const oppositeExists = await exists(opposite)
    signal?.throwIfAborted()
    if (oppositeExists) throw encodingMismatch(opposite, compression)
    const pathExists = await exists(path)
    signal?.throwIfAborted()
    if (pathExists) matches.push(path)
  }
  if (matches.length > 1) {
    throw new Error(`duplicate JSONL session id "${id}" appears in multiple project directories`)
  }
  signal?.throwIfAborted()
  return matches[0]
}

// --- stored-prefix decode ---

/** Opaque coordinator token for replacing bytes recovered from a torn frame. */
export interface JsonlTornMarker {
  truncateTo: number
  recoveredEvents: SessionEvent[]
}

/** One decoded stored prefix, before identity assertion and revision attachment. */
export interface DecodedJsonlPrefix {
  meta: SessionHeader
  events: SessionEvent[]
  tornMarker?: JsonlTornMarker
}

/**
 * Decode one complete or torn JSONL buffer into its preserved event prefix,
 * selecting the physical decoder from `compression`. This is the backend's
 * `readPrefix` inner decode: complete frames plus any complete JSONL records
 * recoverable from a torn final frame.
 * @param buffer - the raw bytes of the log file (header record first).
 * @param compression - physical encoding of `buffer`.
 * @param signal - optional cancellation for the decode work.
 * @returns the header, preserved event prefix, and optional torn-tail marker.
 */
export async function readPrefixBuffer(
  buffer: Buffer,
  compression: JsonlCompression,
  signal?: AbortSignal,
): Promise<DecodedJsonlPrefix> {
  if (compression === 'zstd') return readZstdPrefixBuffer(buffer, signal)
  signal?.throwIfAborted()
  const { meta, events, committedBytes } = scanLog(buffer)
  signal?.throwIfAborted()
  return {
    meta,
    events,
    ...committedBytes < buffer.byteLength
      ? { tornMarker: { truncateTo: committedBytes, recoveredEvents: [] } }
      : {},
  }
}

/** Decode complete frames and retain complete JSONL records from a torn final frame. */
export async function readZstdPrefixBuffer(
  buffer: Buffer,
  signal?: AbortSignal,
): Promise<DecodedJsonlPrefix> {
  signal?.throwIfAborted()
  const { frames, tornStart } = scanZstdFrames(buffer)
  signal?.throwIfAborted()
  if (frames.length === 0) throw new Error('empty or header-less Zstandard session log')

  const decoder = createZstdFrameDecoder()
  let yieldDeadline = performance.now() + ZSTD_DECODE_YIELD_INTERVAL_MS
  try {
    const decodedFrames = decoder.decode(buffer, frames)
    signal?.throwIfAborted()
    const headerFrame = decodedFrames.next()
    signal?.throwIfAborted()
    /* v8 ignore next -- a non-empty structural frame list makes the decoder yield its first frame or throw. */
    if (headerFrame.done) throw new Error('empty or header-less Zstandard session log')
    assertZstdHeaderFrame(headerFrame.value)
    const scanner = new SessionLogScanner(headerFrame.value)

    let remainingFrames = frames.length - 1
    for (const plaintext of decodedFrames) {
      signal?.throwIfAborted()
      scanner.write(plaintext)
      remainingFrames -= 1
      if (remainingFrames > 0 && performance.now() >= yieldDeadline) {
        await scheduler.yield()
        signal?.throwIfAborted()
        yieldDeadline = performance.now() + ZSTD_DECODE_YIELD_INTERVAL_MS
      }
    }
    signal?.throwIfAborted()
    const complete = scanner.checkpoint()
    if (complete.committedBytes !== complete.inputBytes) {
      throw new Error('corrupt Zstandard session log: complete frame contains a torn JSONL record')
    }
    if (tornStart === undefined) {
      const prefix = scanner.finish()
      return { meta: prefix.meta, events: prefix.events }
    }

    let recoveredPlaintext: Buffer = Buffer.alloc(0)
    try {
      signal?.throwIfAborted()
      recoveredPlaintext = await decompressZstdPrefix(buffer.subarray(tornStart))
    } catch {
      /* v8 ignore next -- decoder failure plus concurrent abort is timing-dependent */
      if (signal?.aborted) signal.throwIfAborted()
      // A structurally incomplete final frame may end before Node's decoder can
      // emit any plaintext; the complete prior frames remain recoverable.
    }
    signal?.throwIfAborted()
    scanner.write(recoveredPlaintext)
    const recoveredPrefix = scanner.finish()
    signal?.throwIfAborted()
    return {
      meta: recoveredPrefix.meta,
      events: recoveredPrefix.events,
      tornMarker: {
        truncateTo: tornStart,
        recoveredEvents: recoveredPrefix.events.slice(complete.eventCount),
      },
    }
  } catch (error) {
    /* v8 ignore next -- decoder failure plus concurrent abort is timing-dependent */
    if (signal?.aborted) signal.throwIfAborted()
    throw error
  } finally {
    decoder.close()
  }
}
