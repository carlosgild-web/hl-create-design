import { useCallback, useMemo, useState, type ReactNode } from 'react'

import { I18nContext, translate, type I18n } from './context'
import type { Lang } from './messages'


const STORAGE_KEY = 'hl-create-design.lang'

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'en' || saved === 'es') return saved
  } catch {
    // storage blocked: fall through to the browser language
  }
  return typeof navigator !== 'undefined' && navigator.language.startsWith('es') ? 'es' : 'en'
}

export function I18nProvider({ children, lang: fixed }: { children: ReactNode; lang?: Lang }) {
  const [lang, setLangState] = useState<Lang>(fixed ?? initialLang)
  const setLang = useCallback((next: Lang) => {
    setLangState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // not persisted: the choice still applies to this visit
    }
  }, [])
  const value = useMemo<I18n>(
    () => ({ lang, setLang, t: (key, vars) => translate(lang, key, vars) }),
    [lang, setLang],
  )
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}
