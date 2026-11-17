import { createContext, useContext } from 'react'

import { messages, type Lang, type MessageKey } from './messages'

export type Translate = (key: MessageKey, vars?: Record<string, string | number>) => string
export type I18n = { lang: Lang; setLang: (lang: Lang) => void; t: Translate }

export function translate(lang: Lang, key: MessageKey, vars?: Record<string, string | number>) {
  const text = messages[lang][key] ?? messages.en[key]
  return vars ? text.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? '')) : text
}

export const I18nContext = createContext<I18n | null>(null)

export function useI18n(): I18n {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n needs an I18nProvider')
  return value
}
