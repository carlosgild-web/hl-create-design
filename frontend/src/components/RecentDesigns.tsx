import { useQuery } from '@tanstack/react-query'

import { getRecentDesigns } from '@/api/client'
import type { PreviewTarget } from '@/api/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useI18n } from '@/i18n'

export function RecentDesigns({ onSelect }: { onSelect: (target: PreviewTarget) => void }) {
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
          {recent.data?.map((d) => (
            <li key={`${d.design_number}-${d.revision}-${d.created_at}`}>
              <button
                type="button"
                className="flex w-full items-baseline justify-between gap-3 py-1.5 text-left hover:text-primary disabled:opacity-60"
                disabled={!d.pdf}
                onClick={() =>
                  onSelect({ department: d.department, design_number: d.design_number, revision: d.revision })
                }
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
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
