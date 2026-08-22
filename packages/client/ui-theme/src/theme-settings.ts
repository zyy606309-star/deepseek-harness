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

/** Field carrying the UI font-size scale (`0` = auto, else 0.8..2.0). */
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
export const FONT_SCALE_MAX = 2.0
export const FONT_SCALE_STEP = 0.05

/** Auto-scale bounds: gentler than the manual range so auto never over-scales. */
export const FONT_SCALE_AUTO_MIN = 0.9
export const FONT_SCALE_AUTO_MAX = 1.2

/** Font-scale sentinel: derive the effective scale from the viewport width. */
export const AUTO_FONT_SCALE = 0

/** Default font-size scale (`0` = auto-derived from the viewport). */
export const DEFAULT_FONT_SCALE = AUTO_FONT_SCALE

/** Durable theme section shared by the Host schema and the browser scope. */
export interface ThemeSettings {
  /** Selected built-in preference. */
  preference: ThemePreference
  /** Whole-page background image URL; empty string means none. */
  backgroundImage: string
  /** Whole-page background visibility (0 hides the image, 1 shows it fully). */
  backgroundOpacity: number
  /** UI font-size scale (`0` = auto-derived from the viewport; else explicit 0.8..2.0). */
  fontScale: number
}

/** Durable theme schema; also the wire envelope the browser scope validates against. */
export const ThemeSettingsSchema: z<ThemeSettings> = z.object({
  [THEME_PREFERENCE_FIELD]: z.union([...THEME_PREFERENCES]).default(DEFAULT_PREFERENCE),
  [BACKGROUND_IMAGE_FIELD]: z.string().default(DEFAULT_BACKGROUND_IMAGE),
  [BACKGROUND_OPACITY_FIELD]: z.number().min(0).max(1).default(DEFAULT_BACKGROUND_OPACITY),
  [FONT_SCALE_FIELD]: z.number().min(AUTO_FONT_SCALE).max(FONT_SCALE_MAX).default(AUTO_FONT_SCALE),
})

/**
 * Auto font scale for a viewport width: 1 at 1440px, drifting 0.05 per 480px
 * and clamped to {@link FONT_SCALE_AUTO_MIN}..{@link FONT_SCALE_AUTO_MAX}. A
 * 4K/ultrawide viewport reads larger, a compact laptop smaller, so the same
 * design-system sizes stay legible on any screen.
 * @param viewportWidth - the viewport width in CSS px.
 * @returns the auto scale.
 */
export function autoFontScale(viewportWidth: number): number {
  const scale = 1 + ((viewportWidth - 1440) / 480) * 0.05
  return Math.min(FONT_SCALE_AUTO_MAX, Math.max(FONT_SCALE_AUTO_MIN, scale))
}

/**
 * Resolve the effective font scale: an explicit preference wins; the auto
 * sentinel (`0`) derives from the viewport width.
 * @param scale - the stored preference (`0` = auto).
 * @param viewportWidth - the viewport width in CSS px.
 * @returns the effective scale, clamped to the manual range.
 */
export function resolveFontScale(scale: number, viewportWidth: number): number {
  if (scale === AUTO_FONT_SCALE) return autoFontScale(viewportWidth)
  return Math.min(FONT_SCALE_MAX, Math.max(FONT_SCALE_MIN, scale))
}

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
