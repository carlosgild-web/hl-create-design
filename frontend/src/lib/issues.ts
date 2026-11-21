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
