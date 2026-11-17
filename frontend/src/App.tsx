import { useQuery } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { fetchHealth } from '@/api/health'

// Phase 0 placeholder: the form, assistant and preview arrive in Phase 5 (PLAN.md).
export default function App() {
  const health = useQuery({ queryKey: ['health'], queryFn: fetchHealth, retry: false })

  const status = health.isPending
    ? 'checking…'
    : health.isError
      ? 'not reachable'
      : `ok (v${health.data.version}, LLM: ${health.data.llm_provider})`

  return (
    <main className="mx-auto flex min-h-svh max-w-2xl flex-col justify-center gap-4 px-4">
      <p className="text-sm text-muted-foreground">Hilda &amp; Luna · Ingeniería Electrónica</p>
      <h1 className="font-heading text-3xl font-semibold">Create Design</h1>
      <p>Start a KiCad design with the company title block already filled in.</p>
      <p className="text-sm">
        Backend: <span data-testid="backend-status">{status}</span>
      </p>
      <div>
        <Button variant="outline" onClick={() => health.refetch()}>
          Check again
        </Button>
      </div>
    </main>
  )
}
