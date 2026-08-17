/** Theme preferences stored in the Host user-settings document. */

import z from '@deepseek-ai/schemastery'

/** Built-in preferences accepted at the registry and settings boundaries. */
export const THEME_PREFERENCES = ['light', 'dark', 'system'] as const

/** Settings namespace owned by the theme plugin. */
export const THEME_SETTINGS_NAMESPACE = 'ui-theme'

/** Field carrying the selected built-in theme preference. */
export const THEME_PREFERENCE_FIELD = 'preference'

/** Field carrying the whole-page background image URL (empty string = none). */
export const BACKGROUND_IMAGE_FIELD = 'backgroundImage'

/** Field carrying the whole-page background image opacity (0..1). */
export const BACKGROUND_OPACITY_FIELD = 'backgroundOpacity'

/** Field carrying the UI font-size scale (0.8..1.25, 1 = default). */
export const FONT_SCALE_FIELD = 'fontScale'

/** Theme preference persisted by the product Appearance row. */
export type ThemePreference = typeof THEME_PREFERENCES[number]

/** Default preference when the user-settings document has no override. */
export const DEFAULT_PREFERENCE: ThemePreference = 'system'

/** Default background image: no image. */
export const DEFAULT_BACKGROUND_IMAGE = ''

/** Default background visibility: the image shows at 58% strength. */
export const DEFAULT_BACKGROUND_OPACITY = 0.58

/** Font-size scale bounds (1 = the design-system default size). */
export const FONT_SCALE_MIN = 0.8
export const FONT_SCALE_MAX = 1.25
export const FONT_SCALE_STEP = 0.05
export const DEFAULT_FONT_SCALE = 1

/** Durable theme section shared by the Host schema and the browser scope. */
export interface ThemeSettings {
  /** Selected built-in preference. */
  preference: ThemePreference
  /** Whole-page background image URL; empty string means none. */
  backgroundImage: string
  /** Whole-page background visibility (0 hides the image, 1 shows it fully). */
  backgroundOpacity: number
  /** UI font-size scale (1 = default; range 0.8..1.25). */
  fontScale: number
}

/** Durable theme schema; also the wire envelope the browser scope validates against. */
export const ThemeSettingsSchema: z<ThemeSettings> = z.object({
  [THEME_PREFERENCE_FIELD]: z.union([...THEME_PREFERENCES]).default(DEFAULT_PREFERENCE),
  [BACKGROUND_IMAGE_FIELD]: z.string().default(DEFAULT_BACKGROUND_IMAGE),
  [BACKGROUND_OPACITY_FIELD]: z.number().min(0).max(1).default(DEFAULT_BACKGROUND_OPACITY),
  [FONT_SCALE_FIELD]: z.number().min(FONT_SCALE_MIN).max(FONT_SCALE_MAX).default(DEFAULT_FONT_SCALE),
})

/**
 * Narrow one wire or registry value to a persistable preference.
 * @param value - value crossing the settings or registry boundary.
 * @returns whether the value is a built-in preference.
 */
export function isThemePreference(value: unknown): value is ThemePreference {
  return THEME_PREFERENCES.some(preference => preference === value)
}

/**
 * CSS `url()` value for a background image; an empty string resolves to
 * `none`. Backslashes and quotes are escaped so an image URL cannot break
 * out of the url() string.
 * @param image - the image URL (empty means no image).
 * @returns the CSS value to assign to the background-image variable.
 */
export function backgroundImageCssValue(image: string): string {
  if (image === '') return 'none'
  const escaped = image.replaceAll('\\', '\\\\').replaceAll('"', '\\"')
  return `url("${escaped}")`
}
