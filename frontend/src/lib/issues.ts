import type { Issue } from '@/api/types'
import { translate } from '@/i18n'
import { messages, type Lang, type MessageKey } from '@/i18n/messages'

/** The fields of an issue that its text needs. Older payloads may lack `code` or `params`. */
export type IssueLike = Pick<Issue, 'message'> & { code?: string; params?: Record<string, string> }

/**
 * A rule message in the UI language (decision 0022). The backend sends `code` and `params`
 * with an English `message`; the template is `issue.<code>.<variant>` when the params name a
 * variant, else `issue.<code>`. Without a template the English message is shown.
 */
export function issueText(lang: Lang, issue: IssueLike): string {
  if (!issue.code) return issue.message
  const variant = issue.params?.variant
  const candidates = [variant ? `issue.${issue.code}.${variant}` : '', `issue.${issue.code}`]
  const key = candidates.find((k) => k && k in messages.en) as MessageKey | undefined
  return key ? translate(lang, key, issue.params) : issue.message
}

/**
 * The warnings stored in a card when it was opened (decision 0023): the same read-only check
 * the form runs, so the user sees them before Confirm. The payload's other values are strings.
 */
export function cardWarnings(payload: Record<string, unknown>): Issue[] {
  const warnings = payload.warnings
  return Array.isArray(warnings) ? (warnings as Issue[]) : []
}

const DASHES = /[\u2010\u2011\u2012\u2013\u2014\u2212\ufe63\uff0d]/g

/**
 * Citations as the manual writes them (decision 0024): NFKC, every dash as "-", no spaces
 * inside the brackets. `[02‑revisions#skipped‑letters]` -> `[02-revisions#skipped-letters]`.
 */
export function normalizeRefs(text: string): string {
  return text
    .normalize('NFKC')
    .replace(DASHES, '-')
    .replace(/\[\s*([\w-]+)\s*#\s*([\w-]+)\s*\]/g, '[$1#$2]')
}
