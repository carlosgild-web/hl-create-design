import { useQuery } from '@tanstack/react-query'
import { Eye } from 'lucide-react'

import { getRecentDesigns } from '@/api/client'
import type { PreviewTarget, RecentDesign } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useI18n } from '@/i18n'

type Props = {
  onPreview: (target: PreviewTarget) => void
  /** Inside the Start panel: no card of its own. */
  bare?: boolean
}

const target = (d: RecentDesign): PreviewTarget => ({
  department: d.department,
  design_number: d.design_number,
  revision: d.revision,
  name: d.name,
})

/** The designs created here, newest first; each opens its preview in the dialog. */
export function RecentDesigns({ onPreview, bare = false }: Props) {
  const { t } = useI18n()
  const recent = useQuery({ queryKey: ['recent-designs'], queryFn: getRecentDesigns, retry: false })

  const list = (
    <>
      {recent.data?.length === 0 && <p className="text-sm text-muted-foreground">{t('recent.empty')}</p>}
      <ul className="divide-y text-sm">
        {recent.data?.map((d) => (
          <li key={`${d.design_number}-${d.revision}-${d.created_at}`} className="flex items-center gap-2 py-1.5">
            <span className="min-w-0 flex-1">
              <span className="font-mono">
                {d.design_number} {d.revision}
              </span>{' '}
              <span className="text-muted-foreground">{d.name}</span>
              <span className="block text-xs text-muted-foreground">{d.designer}</span>
            </span>
            {d.pdf ? (
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                aria-label={t('recent.preview_aria', { number: d.design_number, rev: d.revision })}
                title={t('recent.preview_aria', { number: d.design_number, rev: d.revision })}
                onClick={() => onPreview(target(d))}
              >
                <Eye aria-hidden />
              </Button>
            ) : (
              <span className="text-xs text-muted-foreground">{t('recent.no_preview')}</span>
            )}
          </li>
        ))}
      </ul>
    </>
  )

  if (bare) return list
  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-heading text-lg">{t('recent.title')}</CardTitle>
      </CardHeader>
      <CardContent>{list}</CardContent>
    </Card>
  )
}
