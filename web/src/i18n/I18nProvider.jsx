import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import {
  LOCALES,
  STORAGE_KEY,
  detectBrowserLocale,
  interpolate,
  lookup,
  resolveInitialLocale,
  writeStoredLocale,
} from './index.js'

const I18nContext = createContext(null)

export function I18nProvider({ children }) {
  const [locale, setLocaleState] = useState(resolveInitialLocale)
  // 记住这个语言是用户手动选的，还是浏览器推出来的 —— 只有手动选过才写 storage
  const [explicit, setExplicit] = useState(() => {
    try {
      return Boolean(window.localStorage.getItem(STORAGE_KEY))
    } catch {
      return false
    }
  })

  const setLocale = useCallback((next) => {
    setLocaleState(next)
    setExplicit(true)
    writeStoredLocale(next)
  }, [])

  // 用户没手动选过时，跟随浏览器语言变化（多标签页/系统切换语言）
  useEffect(() => {
    if (explicit) return undefined
    const onLangChange = () => {
      const hit = detectBrowserLocale()
      if (hit) setLocaleState(hit)
    }
    window.addEventListener('languagechange', onLangChange)
    return () => window.removeEventListener('languagechange', onLangChange)
  }, [explicit])

  // 让 <html lang> 也跟着走，利于字体回退与无障碍
  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  const value = useMemo(() => {
    const messages = LOCALES[locale].messages
    const t = (key, vars) => {
      const hit = lookup(messages, key)
      if (hit == null) return key // 缺 key 时原样回显，便于发现漏翻
      return interpolate(hit, vars)
    }
    return { locale, setLocale, t, label: LOCALES[locale].label }
  }, [locale, setLocale])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n 必须在 I18nProvider 内使用')
  return ctx
}
