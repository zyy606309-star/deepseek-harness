/** `settings.theme` namespace dictionaries (the Appearance row's copy). */

/** Simplified Chinese dictionary (the key-set source of truth). */
export const zh = {
  'appearance.title': '外观',
  'appearance.light': '浅色',
  'appearance.dark': '深色',
  'appearance.system': '跟随系统',
  'appearance.backgroundImage': '背景图',
  'appearance.backgroundPick': '选择图片',
  'appearance.backgroundClear': '清除',
  'appearance.fontSize': '字体大小',
  'appearance.fontSizeAuto': '自动',
} satisfies Record<string, string>

/** The settings.theme namespace key union. */
export type ThemeKey = keyof typeof zh

/** English dictionary, checked complete against the zh key set. */
export const en = {
  'appearance.title': 'Appearance',
  'appearance.light': 'Light',
  'appearance.dark': 'Dark',
  'appearance.system': 'System',
  'appearance.backgroundImage': 'Background image',
  'appearance.backgroundPick': 'Choose image',
  'appearance.backgroundClear': 'Clear',
  'appearance.fontSize': 'Font size',
  'appearance.fontSizeAuto': 'Auto',
} satisfies Record<ThemeKey, string>
