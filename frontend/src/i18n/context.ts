import { createContext, useContext } from 'react'

import { messages, type Lang, type MessageKey } from './messages'

type Vars = Record<string, string | number>
export type Translate = (key: MessageKey, vars?: Vars) => string

/** Keys that come in plural forms: `<base>.one` and `<base>.other`. */
export type PluralBase = {
  [K in MessageKey]: K extends `${infer B}.one` ? (`${B}.other` extends MessageKey ? B : never) : never
}[MessageKey]
export type TranslatePlural = (base: PluralBase, count: number, vars?: Vars) => string

export type I18n = { lang: Lang; setLang: (lang: Lang) => void; t: Translate; tn: TranslatePlural }

export function translate(lang: Lang, key: MessageKey, vars?: Vars) {
  const text = messages[lang][key] ?? messages.en[key]
  return vars ? text.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? '')) : text
}

/** "1 model call" / "2 model calls" ("1 llamada" / "2 llamadas"); `{count}` is filled in. */
export function translatePlural(lang: Lang, base: PluralBase, count: number, vars?: Vars) {
  const form = new Intl.PluralRules(lang).select(count) === 'one' ? 'one' : 'other'
  return translate(lang, `${base}.${form}` as MessageKey, { ...vars, count })
}

export const I18nContext = createContext<I18n | null>(null)

export function useI18n(): I18n {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n needs an I18nProvider')
  return value
}
