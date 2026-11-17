export type Health = {
  status: string
  version: string
  llm_provider: string
}

export async function fetchHealth(): Promise<Health> {
  const response = await fetch('/api/health')
  if (!response.ok) {
    throw new Error(`Health check failed: HTTP ${response.status}`)
  }
  return response.json() as Promise<Health>
}
