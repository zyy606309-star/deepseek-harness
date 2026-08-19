/**
 * Appearance row slot store: a mirror of the theme service snapshot. The
 * plugin's apply-world change listener is the only writer; the row component
 * reads via props.useStore.
 */
import { defineStore, type EngineStoreHandle } from '@deepseek-ai/dsh-client-runtime/client'
import type { ThemePreference } from '../theme-settings.ts'

/** Store state mirrored from the theme snapshot. */
export interface AppearanceRowState {
  /** Persisted preference (selection state reads this, never the resolved active theme). */
  preference: ThemePreference
  /** Persisted whole-page background image URL. */
  backgroundImage: string
  /** Persisted UI font-size scale (`0` = auto). */
  fontScale: number
  /** Effective scale (the auto resolution when `fontScale` is 0). */
  effectiveFontScale: number
  /** Service revision; -1 until first sync so revision 0 lands as a change. */
  revision: number
}

/** Declared action shape giving the exported factory a stable return type. */
type AppearanceRowActions = {
  sync: (draft: AppearanceRowState, preference: ThemePreference, backgroundImage: string, fontScale: number, effectiveFontScale: number, revision: number) => void
}

/**
 * Declares the Appearance row state and write surface.
 * @returns the store handle.
 */
export function createAppearanceRowStore(): EngineStoreHandle<AppearanceRowState, AppearanceRowActions> {
  return defineStore({
    init: (): AppearanceRowState => ({ preference: 'system', backgroundImage: '', fontScale: 0, effectiveFontScale: 1, revision: -1 }),
    actions: {
      sync: (d, preference, backgroundImage, fontScale, effectiveFontScale, revision) => {
        if (revision <= d.revision) return
        d.preference = preference
        d.backgroundImage = backgroundImage
        d.fontScale = fontScale
        d.effectiveFontScale = effectiveFontScale
        d.revision = revision
      },
    },
  })
}
