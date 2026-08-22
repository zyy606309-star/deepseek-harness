/**
 * Theme bootstrap row for the browser's pre-plugin interval. Each index
 * render embeds the current durable theme settings (preference plus
 * whole-page background and font scale); the browser resolves only `system`,
 * then writes the same DOM fields ui-layout's ThemePresenter owns after the
 * client plugin tree activates.
 */

import type { IndexInjection } from '@deepseek-ai/dsh-host-webserver'
import {
  backgroundImageCssValue,
  DEFAULT_BACKGROUND_IMAGE, DEFAULT_BACKGROUND_OPACITY, DEFAULT_FONT_SCALE,
  DEFAULT_PREFERENCE,
  type ThemeSettings,
} from './theme-settings.ts'

/** Default settings when the Host has no settings provider or no section yet. */
export const DEFAULT_THEME_SETTINGS: ThemeSettings = Object.freeze({
  preference: DEFAULT_PREFERENCE,
  backgroundImage: DEFAULT_BACKGROUND_IMAGE,
  backgroundOpacity: DEFAULT_BACKGROUND_OPACITY,
  fontScale: DEFAULT_FONT_SCALE,
})

/** Build the inline script body for one theme settings section. */
function bootThemeScript(settings: ThemeSettings): string {
  const clamped = Math.min(1, Math.max(0, settings.backgroundOpacity))
  const storedFontScale = settings.fontScale
  const surfaceOpacity = settings.backgroundImage === ''
    ? '100%'
    : `${Math.round((1 - clamped) * 100)}%`
  // The auto formula must match `autoFontScale` in theme-settings.ts; the
  // bootstrap runs before the client plugin tree, so it cannot import it.
  return `(() => {
  const preference = ${JSON.stringify(settings.preference)}
  const systemDark = preference === 'system'
    && typeof matchMedia !== 'undefined'
    && matchMedia('(prefers-color-scheme: dark)').matches
  const dark = preference === 'dark' || systemDark
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
  document.body.toggleAttribute('data-ds-dark-theme', dark)
  document.body.style.setProperty('--dsw-bg-image', ${JSON.stringify(backgroundImageCssValue(settings.backgroundImage))})
  document.body.style.setProperty('--dsw-surface-opacity', ${JSON.stringify(surfaceOpacity)})
  document.body.style.setProperty('--dsw-bg-opacity', ${JSON.stringify(String(clamped))})
  const viewport = document.documentElement.clientWidth || 1440
  const auto = Math.min(1.2, Math.max(0.9, 1 + ((viewport - 1440) / 480) * 0.05))
  const fontScale = ${JSON.stringify(storedFontScale)} === 0 ? auto : ${JSON.stringify(storedFontScale)}
  document.body.style.setProperty('--dsw-font-scale', String(fontScale))
})()`
}

/**
 * The theme bootstrap as an injection row: an inline script immediately after
 * the opening body tag, before the shell mount and module script.
 * @param settings - Current Host-backed theme settings.
 * @returns the body script row.
 */
export function bootThemeInjection(
  settings: ThemeSettings = DEFAULT_THEME_SETTINGS,
): IndexInjection {
  return { kind: 'script', placement: 'body', text: bootThemeScript(settings) }
}
