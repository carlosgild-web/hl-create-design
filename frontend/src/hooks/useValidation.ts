import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { validateFields } from '@/api/client'
import type { FormValues, Validation } from '@/api/types'
import { filledValues } from '@/lib/fields'

export const VALIDATE_DEBOUNCE_MS = 400

/**
 * Inline validation: the filled fields go to `POST /api/validate` 400 ms after the last
 * keystroke. The backend's validators decide (invariant 1); this only shows the result.
 */
export function useValidation(values: FormValues): Validation | undefined {
  // a bare number prefix (HL-HW-26-) is not checked: nothing was typed yet
  const filled = filledValues(values)
  const key = JSON.stringify(filled)
  const [debounced, setDebounced] = useState(key)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(key), VALIDATE_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [key])

  const query = useQuery({
    queryKey: ['validate', debounced],
    queryFn: ({ signal }) => validateFields(JSON.parse(debounced) as Record<string, string>, signal),
    enabled: debounced !== '{}',
    placeholderData: keepPreviousData,
    staleTime: 10_000,
    retry: false,
  })
  return debounced === '{}' ? undefined : query.data
}
