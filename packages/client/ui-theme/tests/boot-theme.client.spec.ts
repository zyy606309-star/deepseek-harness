// @vitest-environment jsdom
/** Host index injection and the resulting pre-plugin browser theme. */
import { runInNewContext } from 'node:vm'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { injectBootTheme } from '../src/boot-theme.ts'
import type { ThemePreference, ThemeSettings } from '../src/theme-settings.ts'

const DARK_ATTRIBUTE = 'data-ds-dark-theme'

function settings(preference: ThemePreference = 'system'): ThemeSettings {
  return { preference, backgroundImage: '', backgroundOpacity: 1, fontScale: 1 }
}

function mockSystemDark(matches: boolean): void {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches }) as MediaQueryList))
}

function executeBootstrap(
  input: ThemeSettings = settings(),
  html = '<html><body><div id="root"></div><script type="module"></script></body></html>',
): string {
  const injected = injectBootTheme(html, input)
  const source = /<script>([\s\S]*?)<\/script>/.exec(injected)?.[1]
  if (source === undefined) throw new Error('theme bootstrap script missing')
  runInNewContext(source, { document, matchMedia: globalThis.matchMedia })
  return injected
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  document.documentElement.style.removeProperty('color-scheme')
  document.body.removeAttribute(DARK_ATTRIBUTE)
  document.body.style.removeProperty('--dsw-bg-image')
  document.body.style.removeProperty('--dsw-surface-opacity')
  document.body.style.removeProperty('--dsw-font-scale')
})

describe('theme boot index transform', () => {
  it('runs immediately inside the body before the shell mount', () => {
    mockSystemDark(false)
    const html = executeBootstrap(settings('dark'), '<html><body class="app"><div id="root"></div></body></html>')
    expect(html.indexOf('<script>')).toBeGreaterThan(html.indexOf('<body class="app">'))
    expect(html.indexOf('<script>')).toBeLessThan(html.indexOf('<div id="root">'))
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

  it('appends the script to a body-less fragment', () => {
    const html = injectBootTheme('<main>loading</main>', settings('dark'))
    expect(html.startsWith('<main>loading</main><script>')).toBe(true)
  })
})
