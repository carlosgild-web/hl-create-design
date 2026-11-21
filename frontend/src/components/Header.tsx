import { useQuery } from '@tanstack/react-query'

import { getHealth } from '@/api/client'
import { Button } from '@/components/ui/button'
import { DemoGuide } from '@/demo-guide/DemoGuide'
import { useI18n } from '@/i18n'

export function Header() {
  const { t, lang, setLang } = useI18n()
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, staleTime: 60_000, retry: false })
  const demo = health.data?.llm_provider === 'demo'

  return (
    <header>
      <DemoGuide />
      <div className="mx-auto flex max-w-[100rem] items-center justify-between gap-4 px-4 py-4 lg:py-2.5">
        <div className="flex items-center gap-3">
          <img src="/favicon.svg" alt="" className="size-9 rounded lg:size-8" />
          <div className="lg:flex lg:items-baseline lg:gap-3">
            <h1 className="font-heading text-xl font-semibold lg:order-2 lg:text-lg">{t('app.title')}</h1>
            <p className="text-xs text-muted-foreground lg:order-1">{t('app.company')}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
        {demo && (
          <span role="status" className="rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground">
            {t('header.demo')}
          </span>
        )}
        <div role="group" aria-label={t('lang.label')} className="flex gap-1">
          {(['en', 'es'] as const).map((code) => (
            <Button
              key={code}
              size="sm"
              variant={lang === code ? 'default' : 'outline'}
              aria-pressed={lang === code}
              onClick={() => setLang(code)}
            >
              {code.toUpperCase()}
            </Button>
          ))}
        </div>
        </div>
      </div>
    </header>
  )
}
