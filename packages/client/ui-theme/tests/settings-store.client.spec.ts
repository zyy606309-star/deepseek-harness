/** Appearance row store: snapshot-mirror action and the revision guard. */
import { describe, expect, it } from 'vitest'
import { createAppearanceRowStore } from '../src/client/settings-store.ts'

describe('createAppearanceRowStore', () => {
  it('init shape: system preference, no background, revision at -1', () => {
    const store = createAppearanceRowStore().create()
    expect(store.getSnapshot()).toEqual({ preference: 'system', backgroundImage: '', fontScale: 1, revision: -1 })
  })

  it('sync mirrors the preference and background and advances the revision', () => {
    const store = createAppearanceRowStore().create()
    store.actions.sync('dark', 'https://example.com/bg.png', 1, 0)
    expect(store.getSnapshot()).toEqual({ preference: 'dark', backgroundImage: 'https://example.com/bg.png', fontScale: 1, revision: 0 })
    store.actions.sync('light', '', 1, 2)
    expect(store.getSnapshot().preference).toBe('light')
    expect(store.getSnapshot().backgroundImage).toBe('')
    expect(store.getSnapshot().revision).toBe(2)
  })

  it('revision guard drops stale and duplicate writes', () => {
    const store = createAppearanceRowStore().create()
    store.actions.sync('dark', 'a', 1, 3)
    store.actions.sync('system', 'b', 1, 2)
    store.actions.sync('system', 'b', 1, 3)
    expect(store.getSnapshot().preference).toBe('dark')
    expect(store.getSnapshot().backgroundImage).toBe('a')
    expect(store.getSnapshot().revision).toBe(3)
  })
})
