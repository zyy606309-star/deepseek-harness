/**
 * Global theme DOM applier: projects the resolved ThemeSnapshot onto the
 * document — `html { color-scheme }` for native UA chrome (scrollbars, form
 * controls), `body[data-ds-dark-theme]` for the token palette, the active
 * theme's alias-token overrides as inline CSS variables on body, the
 * whole-page background image + surface-opacity variables, and one
 * presenter-owned `meta[name="theme-color"]` for surrounding browser UI. Pure
 * DOM writes, no React involvement; the presenter only ever retracts what it
 * wrote itself, so foreign attributes, metadata, and inline styles survive.
 */
import type { ThemeSnapshot } from '@deepseek-ai/dsh-client-ui-theme/client'

/** Body attribute selecting the dark base palette in the token stylesheets. */
export const DARK_ATTRIBUTE = 'data-ds-dark-theme'

/** Body custom property holding the background image `url()` (or `none`). */
export const BACKGROUND_IMAGE_VARIABLE = '--dsw-bg-image'

/** Body custom property holding the content-surface opacity (a percentage). */
export const SURFACE_OPACITY_VARIABLE = '--dsw-surface-opacity'

/** Body custom property holding the background image opacity (0..1). */
export const BACKGROUND_OPACITY_VARIABLE = '--dsw-bg-opacity'

/** Body custom property holding the UI font-size scale. */
export const FONT_SCALE_VARIABLE = '--dsw-font-scale'

/**
 * CSS `url()` value for a background image; an empty string resolves to
 * `none`. Backslashes and quotes are escaped so an image URL cannot break
 * out of the url() string.
 * @param image - the image URL (empty means no image).
 * @returns the CSS value to assign to the background-image variable.
 */
function backgroundImageCssValue(image: string): string {
  if (image === '') return 'none'
  const escaped = image.replaceAll('\\', '\\\\').replaceAll('"', '\\"')
  return `url("${escaped}")`
}

/**
 * Content-surface opacity for a background visibility level: higher visibility
 * makes the surfaces more transparent so the image shows through.
 * @param opacity - background visibility, clamped to 0..1.
 * @returns the CSS percentage to assign to the surface-opacity variable.
 */
function surfaceOpacityValue(opacity: number): string {
  const percent = Math.round((1 - Math.min(1, Math.max(0, opacity))) * 100)
  return `${percent}%`
}

/** Applies theme snapshots to the document; one instance per plugin fiber. */
export class ThemePresenter {
  /** Token names this presenter wrote in the last apply (its retraction set). */
  private appliedTokens: string[] = []
  /** The single metadata node this presenter inserts and removes. */
  private readonly themeColorMeta: HTMLMetaElement

  /** Create the presenter-owned metadata node before the first snapshot arrives. */
  constructor() {
    this.themeColorMeta = document.createElement('meta')
    this.themeColorMeta.name = 'theme-color'
  }

  /**
   * Project a snapshot onto the document: set root `color-scheme` and the body
   * palette attribute from `active.colorScheme` (never the id — `system` is
   * resolved upstream), then replace the previously applied token variables
   * with `active.tokens`, then set the background image and surface-opacity
   * variables. Browser theme-color metadata follows the computed body
   * background after those writes, so the rendered palette remains the color
   * authority.
   * @param snapshot - resolved theme snapshot from ctx.theme.
   */
  apply(snapshot: ThemeSnapshot): void {
    const scheme = snapshot.active.colorScheme
    document.documentElement.style.colorScheme = scheme
    const body = document.body
    if (scheme === 'dark') body.setAttribute(DARK_ATTRIBUTE, '')
    else body.removeAttribute(DARK_ATTRIBUTE)
    for (const name of this.appliedTokens) body.style.removeProperty(name)
    this.appliedTokens = []
    for (const [name, value] of Object.entries(snapshot.active.tokens)) {
      body.style.setProperty(name, value)
      this.appliedTokens.push(name)
    }
    const image = snapshot.background.image
    body.style.setProperty(BACKGROUND_IMAGE_VARIABLE, backgroundImageCssValue(image))
    body.style.setProperty(SURFACE_OPACITY_VARIABLE, image === '' ? '100%' : surfaceOpacityValue(snapshot.background.opacity))
    body.style.setProperty(BACKGROUND_OPACITY_VARIABLE, String(snapshot.background.opacity))
    body.style.setProperty(FONT_SCALE_VARIABLE, String(snapshot.fontScale))
    this.themeColorMeta.content = getComputedStyle(body).backgroundColor
    if (!this.themeColorMeta.isConnected) document.head.append(this.themeColorMeta)
  }

  /** Retract root color-scheme, the palette attribute, token variables, the background variables, and the owned metadata node. */
  dispose(): void {
    document.documentElement.style.removeProperty('color-scheme')
    const body = document.body
    body.removeAttribute(DARK_ATTRIBUTE)
    for (const name of this.appliedTokens) body.style.removeProperty(name)
    this.appliedTokens = []
    body.style.removeProperty(BACKGROUND_IMAGE_VARIABLE)
    body.style.removeProperty(SURFACE_OPACITY_VARIABLE)
    body.style.removeProperty(BACKGROUND_OPACITY_VARIABLE)
    body.style.removeProperty(FONT_SCALE_VARIABLE)
    this.themeColorMeta.remove()
  }
}
