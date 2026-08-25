import { describe, expect, it } from 'vitest'
import {
  CENTER_MIN, clampWidth, computeColumns,
  DETAILS_DEFAULT, DETAILS_MIN, SIDEBAR_COLLAPSED, SIDEBAR_DEFAULT, SIDEBAR_MAX, SIDEBAR_MIN, sidebarDefault,
} from '@deepseek-ai/dsh-client-ui-layout/src/client/columns.ts'

// Numeric preference form (0 = closed); helpers keep the scenario names readable.
const open = (width: number) => width
const closed = (_width: number) => 0

describe('clampWidth', () => {
  it('clamps into the range and rounds', () => {
    expect(clampWidth(250.4, 240, 420)).toBe(250)
    expect(clampWidth(100, 240, 420)).toBe(240)
    expect(clampWidth(9999, 240, 420)).toBe(420)
  })
})

describe('sidebarDefault', () => {
  it('holds the contract default at and below the auto-collapse breakpoint', () => {
    expect(sidebarDefault(1024)).toBe(SIDEBAR_DEFAULT)
    expect(sidebarDefault(800)).toBe(SIDEBAR_DEFAULT)
  })

  it('grows linearly across the desktop range, wider than the fixed floor', () => {
    // 1440px desktop opens a clearly wider pane than the default floor.
    const d1440 = sidebarDefault(1440)
    expect(d1440).toBeGreaterThan(SIDEBAR_DEFAULT)
    expect(d1440).toBe(374)
    // Increasing width never shrinks the default.
    expect(sidebarDefault(1600)).toBeGreaterThan(d1440)
  })

  it('caps at the drag ceiling on an ultrawide', () => {
    expect(sidebarDefault(2100)).toBe(460)
    expect(sidebarDefault(2560)).toBe(460)
  })
})

describe('computeColumns', () => {
  it('step 1: everything fits at preferred widths', () => {
    const cols = computeColumns(1920, open(SIDEBAR_DEFAULT), open(DETAILS_DEFAULT))
    expect(cols).toEqual({ sidebar: SIDEBAR_DEFAULT, center: 1920 - SIDEBAR_DEFAULT - 360, details: 360 })
  })

  it('closed sidebar keeps its compact rail while closed details contribute zero width', () => {
    expect(computeColumns(1920, closed(300), closed(360)))
      .toEqual({ sidebar: SIDEBAR_COLLAPSED, center: 1920 - SIDEBAR_COLLAPSED, details: 0 })
  })

  it('preferences beyond the clamp range are clamped before solving', () => {
    const cols = computeColumns(1920, open(9999), open(1))
    expect(cols.sidebar).toBe(SIDEBAR_MAX)
    expect(cols.details).toBe(300)
    expect(computeColumns(1920, open(1), open(DETAILS_DEFAULT)).sidebar).toBe(SIDEBAR_MIN)
  })

  it('step 2: details shrinks first, center pinned at min', () => {
    // 320 + 360 + 640 = 1320 > 1280; details concedes to 1280-320-640 = 320.
    const cols = computeColumns(1280, open(SIDEBAR_DEFAULT), open(DETAILS_DEFAULT))
    expect(cols).toEqual({ sidebar: SIDEBAR_DEFAULT, center: CENTER_MIN, details: 320 })
  })

  it('boundary: exactly at the step-1/step-2 seam', () => {
    const cols = computeColumns(300 + 360 + CENTER_MIN, open(300), open(360))
    expect(cols).toEqual({ sidebar: 300, center: CENTER_MIN, details: 360 })
    const one = computeColumns(300 + 360 + CENTER_MIN - 1, open(300), open(360))
    expect(one).toEqual({ sidebar: 300, center: CENTER_MIN, details: 359 })
  })

  it('step 3: details auto-closes when its min still starves center — sidebar holds its preference', () => {
    // 320 + 300 + 640 = 1260 > 1210 → details 0; sidebar untouched: center = 1210-320 = 890.
    const cols = computeColumns(1210, open(SIDEBAR_DEFAULT), open(DETAILS_DEFAULT))
    expect(cols).toEqual({ sidebar: SIDEBAR_DEFAULT, center: 890, details: 0 })
  })

  it('the sidebar never concedes: center absorbs the deficit below CENTER_MIN', () => {
    const cols = computeColumns(700, open(SIDEBAR_DEFAULT), closed(DETAILS_DEFAULT))
    expect(cols).toEqual({ sidebar: SIDEBAR_DEFAULT, center: 700 - SIDEBAR_DEFAULT, details: 0 })
  })

  it('sidebar-closed narrow window: details concedes then auto-closes', () => {
    const fits = computeColumns(SIDEBAR_COLLAPSED + DETAILS_MIN + CENTER_MIN, closed(300), open(DETAILS_DEFAULT))
    expect(fits).toEqual({ sidebar: SIDEBAR_COLLAPSED, center: CENTER_MIN, details: DETAILS_MIN })
    const starved = computeColumns(SIDEBAR_COLLAPSED + DETAILS_MIN + CENTER_MIN - 1, closed(300), open(DETAILS_DEFAULT))
    expect(starved).toEqual({
      sidebar: SIDEBAR_COLLAPSED,
      center: DETAILS_MIN + CENTER_MIN - 1,
      details: 0,
    })
  })

  it('tiny viewport: details closes, sidebar holds, center takes the remainder', () => {
    const cols = computeColumns(400, open(SIDEBAR_DEFAULT), open(DETAILS_DEFAULT))
    expect(cols.details).toBe(0)
    expect(cols.sidebar).toBe(SIDEBAR_DEFAULT)
    expect(cols.center).toBe(Math.max(0, 400 - SIDEBAR_DEFAULT))
  })

  it('recovery is pure: re-widening restores preferred widths untouched', () => {
    const squeezed = computeColumns(1100, open(SIDEBAR_DEFAULT), open(DETAILS_DEFAULT))
    expect(squeezed.details).toBe(0)
    const restored = computeColumns(1920, open(SIDEBAR_DEFAULT), open(DETAILS_DEFAULT))
    expect(restored.details).toBe(DETAILS_DEFAULT)
    expect(restored.sidebar).toBe(SIDEBAR_DEFAULT)
  })
})

describe('computeColumns — degenerate viewports', () => {
  it('sidebar closed and viewport below CENTER_MIN: details auto-closes, center takes the rest', () => {
    // Reaches step 3's auto-close with the compact rail sidebar.
    expect(computeColumns(500, closed(300), open(DETAILS_DEFAULT)))
      .toEqual({ sidebar: SIDEBAR_COLLAPSED, center: 500 - SIDEBAR_COLLAPSED, details: 0 })
  })
})
