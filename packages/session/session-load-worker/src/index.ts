/**
 * Worker-thread cold loader for bounded session-history pages. The JSONL
 * decode and persistence normalization run inside a worker; the full decoded
 * log stays there and only the page crosses the boundary.
 * @module @deepseek-ai/dsh-session-load-worker
 */

export { DEFAULT_MAX_MESSAGES, loadSessionPage } from './host.ts'
export type { LoadedPage, LoadRequest } from './protocol.ts'
export type { JsonlCompression } from '@deepseek-ai/dsh-session-persistence-jsonl/format'
