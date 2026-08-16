/**
 * Appearance preference row registered into the General section item slot
 * (figma 501:30012 'Frame 2117131228'): title + three preference cubes plus
 * the whole-page background controls. Registered by this package — the theme
 * feature owns its own settings surface. Selection follows the persisted
 * preference, never the resolved active theme.
 */
import { useRef } from 'react'
import type { ChangeEvent } from 'react'
import clsx from 'clsx'
import {
  IconDarkOutline16, IconFollowsystemOutline16, IconLightOutline16,
} from '@deepseek-ai/dsh-client-ui-primitives'
import type { PropsLocale, PropsRuntime, PropsStore } from '@deepseek-ai/dsh-client-ui-slots'
import type { ThemePreference } from '../theme-settings.ts'
import type { ThemeKey } from './locales.ts'
import type {} from '@deepseek-ai/dsh-client-ui-settings/client'
import type { createAppearanceRowStore } from './settings-store.ts'
import css from './AppearanceRow.module.css'

/** Injected business face: the preference and background writes (t rides the standard locale seat). */
export interface AppearanceRowInjected {
  /** Switch the theme preference. */
  setTheme: (id: ThemePreference) => void
  /** Set the whole-page background image (a URL or data URL). */
  setBackgroundImage: (image: string) => void
}

/** Full component props: runtime share + store share + locale seat + injected face. */
export type AppearanceRowComponentProps =
  PropsRuntime<'settings.general.item'> & PropsStore<ReturnType<typeof createAppearanceRowStore>>
  & PropsLocale<'settings.theme'> & AppearanceRowInjected

/** Cube order and icons (figma 501:30015-30017: Light, Dark, System). */
const CUBES: readonly { id: ThemePreference; labelKey: ThemeKey; Icon: typeof IconLightOutline16 }[] = [
  { id: 'light', labelKey: 'appearance.light', Icon: IconLightOutline16 },
  { id: 'dark', labelKey: 'appearance.dark', Icon: IconDarkOutline16 },
  { id: 'system', labelKey: 'appearance.system', Icon: IconFollowsystemOutline16 },
]

/** Longest edge cap for a picked background image, in pixels. */
const BACKGROUND_MAX_EDGE = 1920

/**
 * Downscale an image to a bounded JPEG data URL. A full-resolution photo can
 * produce a multi-megabyte data URL that the settings wire cannot round-trip;
 * this keeps the persisted value small enough to read back.
 * @param src - decoded image source (data URL).
 * @param apply - receives the compressed data URL.
 * @param fallback - receives the original source when compression is unavailable.
 */
function compressBackground(src: string, apply: (dataUrl: string) => void, fallback: (src: string) => void): void {
  const image = new Image()
  image.onload = () => {
    const scale = Math.min(1, BACKGROUND_MAX_EDGE / Math.max(image.width, image.height))
    const width = Math.max(1, Math.round(image.width * scale))
    const height = Math.max(1, Math.round(image.height * scale))
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d')
    if (context === null) { fallback(src); return }
    context.drawImage(image, 0, 0, width, height)
    apply(canvas.toDataURL('image/jpeg', 0.85))
  }
  image.onerror = () => { fallback(src) }
  image.src = src
}

/**
 * Render the Appearance row.
 * @param props - composed slot props.
 * @returns the row element tree.
 */
export function AppearanceRow({ t, setTheme, setBackgroundImage, useStore }: AppearanceRowComponentProps) {
  const preference = useStore(s => s.preference)
  const backgroundImage = useStore(s => s.backgroundImage)
  const fileInput = useRef<HTMLInputElement>(null)

  /** Read the picked image, compress it, and apply it as the background. */
  const onFilePicked = (event: ChangeEvent<HTMLInputElement>): void => {
    const file = event.target.files?.[0]
    // Reset so re-picking the same file still fires a change.
    event.target.value = ''
    if (file === undefined) return
    const reader = new FileReader()
    reader.onload = () => {
      const src = typeof reader.result === 'string' ? reader.result : ''
      if (src === '') return
      compressBackground(src, setBackgroundImage, setBackgroundImage)
    }
    reader.readAsDataURL(file)
  }

  return (
    <div className={css.group}>
      <div className={css.title}>{t('appearance.title')}</div>
      <div className={css.cubeRow}>
        {CUBES.map(({ id, labelKey, Icon }) => (
          <button
            key={id}
            type="button"
            className={clsx(css.themeCube, preference === id && css.selected)}
            aria-pressed={preference === id}
            onClick={() => { setTheme(id) }}
          >
            <Icon />
            {t(labelKey)}
          </button>
        ))}
      </div>
      <label className={css.fieldLabel}>{t('appearance.backgroundImage')}</label>
      <div className={css.backgroundRow}>
        <button type="button" className={css.pickButton} onClick={() => { fileInput.current?.click() }}>
          {t('appearance.backgroundPick')}
        </button>
        {backgroundImage !== '' && (
          <button type="button" className={css.clearButton} onClick={() => { setBackgroundImage('') }}>
            {t('appearance.backgroundClear')}
          </button>
        )}
      </div>
      {backgroundImage !== '' && <img className={css.preview} src={backgroundImage} alt="" />}
      <input
        ref={fileInput}
        className={css.hiddenFileInput}
        type="file"
        accept="image/*"
        onChange={onFilePicked}
      />
    </div>
  )
}
