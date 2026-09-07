import enUS from './locales/en-US.js'
import jaJP from './locales/ja-JP.js'
import zhTW from './locales/zh-TW.js'

export const LOCALES = {
  'zh-TW': { label: '繁體中文', short: '繁', messages: zhTW },
  'en-US': { label: 'English', short: 'EN', messages: enUS },
  'ja-JP': { label: '日本語', short: '日', messages: jaJP },
}

export const SUPPORTED = Object.keys(LOCALES)
export const DEFAULT_LOCALE = 'ja-JP'
export const STORAGE_KEY = 'reid.locale'

/**
 * 把浏览器给的语言标签归一到我们支持的三档。
 * 例：zh-Hant-TW / zh-TW / zh-HK -> zh-TW；zh-CN -> 兜底（不支持简体，回落默认）；
 *     en-GB -> en-US；ja -> ja-JP。
 */
export function normalizeLocale(tag) {
  if (!tag) return null
  const t = String(tag).toLowerCase()
  if (t.startsWith('zh')) {
    // 繁体（台湾/香港/澳门）归到 zh-TW；简体不在支持列表内
    if (/(hant|tw|hk|mo)/.test(t)) return 'zh-TW'
    return null
  }
  if (t.startsWith('en')) return 'en-US'
  if (t.startsWith('ja')) return 'ja-JP'
  return null
}

/** 依次尝试 navigator.languages / navigator.language，读不到就返回 null。 */
export function detectBrowserLocale() {
  if (typeof navigator === 'undefined') return null
  const candidates = [
    ...(Array.isArray(navigator.languages) ? navigator.languages : []),
    navigator.language,
    navigator.userLanguage,
  ]
  for (const c of candidates) {
    const hit = normalizeLocale(c)
    if (hit) return hit
  }
  return null
}

export function readStoredLocale() {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    return SUPPORTED.includes(saved) ? saved : null
  } catch {
    return null // 隐私模式 / 禁用了 storage
  }
}

/**
 * 读 URL 上的 ?locale=en-US —— 仅用于截图/分享，不写 storage。
 * 优先于用户已保存的选择，方便一条链接直接出指定语言。
 */
export function readQueryLocale() {
  try {
    const hit = new URLSearchParams(window.location.search).get('locale')
    return SUPPORTED.includes(hit) ? hit : null
  } catch {
    return null
  }
}

export function writeStoredLocale(locale) {
  try {
    window.localStorage.setItem(STORAGE_KEY, locale)
  } catch {
    /* 忽略写入失败，语言仍在本会话生效 */
  }
}

/** 优先级：URL ?locale= > localStorage 里用户显式选过的 > 浏览器语言 > ja-JP */
export function resolveInitialLocale() {
  return readQueryLocale() || readStoredLocale() || detectBrowserLocale() || DEFAULT_LOCALE
}

/** 取嵌套 key：t('search.params') */
export function lookup(messages, key) {
  return key.split('.').reduce((acc, part) => (acc == null ? undefined : acc[part]), messages)
}

/** 支持 {name} 占位符与复数无关的简单插值。 */
export function interpolate(text, vars) {
  if (!vars) return text
  return text.replace(/\{(\w+)\}/g, (m, k) => (vars[k] == null ? m : String(vars[k])))
}
