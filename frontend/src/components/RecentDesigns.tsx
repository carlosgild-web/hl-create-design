import { useQuery } from '@tanstack/react-query'

import { getRecentDesigns } from '@/api/client'
import type { PreviewTarget } from '@/api/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'

type Props = { selected?: PreviewTarget | null; onSelect: (target: PreviewTarget) => void }

const same = (a: PreviewTarget | null | undefined, b: PreviewTarget) =>
  !!a && a.department === b.department && a.design_number === b.design_number && a.revision === b.revision

export function RecentDesigns({ selected, onSelect }: Props) {
  const { t } = useI18n()
  const recent = useQuery({ queryKey: ['recent-designs'], queryFn: getRecentDesigns, retry: false })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-heading text-lg">{t('recent.title')}</CardTitle>
      </CardHeader>
      <CardContent>
        {recent.data?.length === 0 && <p className="text-sm text-muted-foreground">{t('recent.empty')}</p>}
        <ul className="divide-y text-sm">
          {recent.data?.map((d) => {
            const target = { department: d.department, design_number: d.design_number, revision: d.revision }
            const current = same(selected, target)
            return (
              <li key={`${d.design_number}-${d.revision}-${d.created_at}`}>
                <button
                  type="button"
                  aria-current={current || undefined}
                  className={cn(
                    'flex w-full items-baseline justify-between gap-3 rounded-md px-2 py-1.5 text-left hover:text-primary disabled:opacity-60',
                    current && 'bg-secondary font-medium text-primary',
                  )}
                  disabled={!d.pdf}
                  onClick={() => onSelect(target)}
                >
                  <span>
                    <span className="font-mono">
                      {d.design_number} {d.revision}
                    </span>{' '}
                    <span className="text-muted-foreground">{d.name}</span>
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">{d.designer}</span>
                </button>
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}
