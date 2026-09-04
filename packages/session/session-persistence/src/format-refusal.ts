/**
 * Format-refusal vocabulary shared by the persistence coordinator and any
 * worker-side cold loader that reads the same stored log. The coordinator and
 * the package root re-export these so the Service Definition keeps one import
 * home.
 * @module @deepseek-ai/dsh-session-persistence/format-refusal
 */

import { SESSION_FORMAT_VERSION } from '@deepseek-ai/dsh-session'
import type { SessionLocation } from './index.ts'

/**
 * The stored log is intact but this runtime cannot faithfully interpret it:
 * the header carries an unsupported format version, or an event's type is
 * unknown to this build and the event is not marked ignorable. Distinct from
 * `SessionPersistenceCorruptionError` — nothing is damaged; the raw log
 * remains readable at {@link location} when the backend keeps one artifact
 * per session.
 */
export class SessionFormatUnsupportedError extends Error {
  /**
   * @param message - stable reason the log cannot be interpreted, already
   *   including the raw-log path when one exists.
   * @param location - the backend's artifact location, when one exists.
   */
  constructor(message: string, readonly location?: SessionLocation) {
    super(message)
    this.name = 'SessionFormatUnsupportedError'
  }
}

/**
 * Direction-aware refusal text for a stored session whose format version this
 * build does not read. Shared by the coordinator's load-time check and by
 * backends that must refuse BEFORE decoding version-dependent structure (a
 * future format may not satisfy today's structural checks at all, and the
 * user must see "upgrade the harness", never "corrupt").
 * @param id - the stored session id, for message context.
 * @param version - the stored format version.
 * @returns the stable refusal text, without a raw-log path suffix.
 */
export function sessionFormatVersionRefusal(id: string, version: number): string {
  return version > SESSION_FORMAT_VERSION
    ? `session "${id}" uses log format v${version}, but this harness reads only v${SESSION_FORMAT_VERSION}: the log was written by a newer harness — upgrade the harness to open it`
    : `session "${id}" uses log format v${version}, older than the supported v${SESSION_FORMAT_VERSION}, and this build ships no upgrade path for it`
}
