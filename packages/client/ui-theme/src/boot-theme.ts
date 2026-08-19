/**
 * Host-rendered theme bootstrap for the browser's pre-plugin interval. Each
 * index response embeds the current durable theme settings (preference plus
 * whole-page background); the browser resolves only `system`, then writes the
 * same DOM fields ui-layout's ThemePresenter owns after the client plugin tree
 * activates.
 */

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

/** Build the inline script for one theme settings section. */
function bootThemeScript(settings: ThemeSettings): string {
  const clamped = Math.min(1, Math.max(0, settings.backgroundOpacity))
  const storedFontScale = settings.fontScale
  const surfaceOpacity = settings.backgroundImage === ''
    ? '100%'
    : `${Math.round((1 - clamped) * 100)}%`
  // The auto formula must match `autoFontScale` in theme-settings.ts; the
  // bootstrap runs before the client plugin tree, so it cannot import it.
  return `<script>(() => {
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
})()</script>`
}

/**
 * Insert the theme bootstrap immediately after the opening body tag, before
 * the shell mount and module script. Body-less fragments receive it at the
 * end, where the HTML parser has already synthesized a body.
 * @param html - Raw application index HTML.
 * @param settings - Current Host-backed theme settings.
 * @returns HTML containing the theme bootstrap.
 */
export function injectBootTheme(
  html: string,
  settings: ThemeSettings = DEFAULT_THEME_SETTINGS,
): string {
  const script = bootThemeScript(settings)
  const body = /<body(?:\s[^>]*)?>/i.exec(html)
  if (body === null) return `${html}${script}`
  const at = body.index + body[0].length
  return `${html.slice(0, at)}${script}${html.slice(at)}`
}
