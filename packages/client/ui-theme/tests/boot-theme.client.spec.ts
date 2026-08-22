// @vitest-environment jsdom
/** The theme bootstrap injection row and the resulting pre-plugin browser theme. */
import { runInNewContext } from 'node:vm'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { bootThemeInjection } from '../src/boot-theme.ts'
import type { ThemePreference, ThemeSettings } from '../src/theme-settings.ts'

const DARK_ATTRIBUTE = 'data-ds-dark-theme'

function settings(preference: ThemePreference = 'system'): ThemeSettings {
  return { preference, backgroundImage: '', backgroundOpacity: 1, fontScale: 1 }
}

function mockSystemDark(matches: boolean): void {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches }) as MediaQueryList))
}

function executeBootstrap(input: ThemeSettings = settings()): void {
  const row = bootThemeInjection(input)
  if (row.kind !== 'script') throw new Error('theme bootstrap row is not a script')
  runInNewContext(row.text, { document, matchMedia: globalThis.matchMedia })
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  document.documentElement.style.removeProperty('color-scheme')
  document.body.removeAttribute(DARK_ATTRIBUTE)
  document.body.style.removeProperty('--dsw-bg-image')
  document.body.style.removeProperty('--dsw-surface-opacity')
  document.body.style.removeProperty('--dsw-bg-opacity')
  document.body.style.removeProperty('--dsw-font-scale')
})

describe('theme bootstrap row', () => {
  it('is a body script row, so it runs before the shell mount', () => {
    mockSystemDark(false)
    const row = bootThemeInjection(settings('dark'))
    expect(row).toMatchObject({ kind: 'script', placement: 'body' })
    executeBootstrap(settings('dark'))
    expect(document.documentElement.style.colorScheme).toBe('dark')
    expect(document.body.hasAttribute(DARK_ATTRIBUTE)).toBe(true)
  })

  it('lets durable light override a dark OS and clears stale dark state', () => {
    document.body.setAttribute(DARK_ATTRIBUTE, '')
    mockSystemDark(true)
    executeBootstrap(settings('light'))
    expect(document.documentElement.style.colorScheme).toBe('light')
    expect(document.body.hasAttribute(DARK_ATTRIBUTE)).toBe(false)
  })

  it.each([
    [true, 'dark', true],
    [false, 'light', false],
  ] as const)('resolves system=%s to %s', (matches, colorScheme, dark) => {
    mockSystemDark(matches)
    executeBootstrap(settings('system'))
    expect(document.documentElement.style.colorScheme).toBe(colorScheme)
    expect(document.body.hasAttribute(DARK_ATTRIBUTE)).toBe(dark)
  })

  it('defaults to system and falls back to light when matchMedia is unavailable', () => {
    vi.stubGlobal('matchMedia', undefined)
    executeBootstrap()
    expect(document.documentElement.style.colorScheme).toBe('light')
    expect(document.body.hasAttribute(DARK_ATTRIBUTE)).toBe(false)
  })

  it('applies the durable background before the shell mounts', () => {
    mockSystemDark(false)
    executeBootstrap({ preference: 'system', backgroundImage: 'https://example.com/bg.png', backgroundOpacity: 0.5, fontScale: 1.1 })
    expect(document.body.style.getPropertyValue('--dsw-bg-image')).toBe('url("https://example.com/bg.png")')
    expect(document.body.style.getPropertyValue('--dsw-surface-opacity')).toBe('50%')
  })
})
