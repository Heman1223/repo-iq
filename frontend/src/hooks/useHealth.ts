/** Polls `GET /health` once on mount to drive the top-bar status pill. */

import { useEffect, useState } from 'react'

import { getHealth } from '@/lib/api'
import type { HealthResponse } from '@/types'

export type BackendState = 'checking' | 'online' | 'degraded' | 'offline'

export interface UseHealthResult {
  state: BackendState
  health: HealthResponse | null
}

export function useHealth(): UseHealthResult {
  const [state, setState] = useState<BackendState>('checking')
  const [health, setHealth] = useState<HealthResponse | null>(null)

  useEffect(() => {
    let cancelled = false

    getHealth()
      .then((response) => {
        if (cancelled) return
        setHealth(response)
        setState(response.llm_configured ? 'online' : 'degraded')
      })
      .catch(() => {
        if (!cancelled) setState('offline')
      })

    return () => {
      cancelled = true
    }
  }, [])

  return { state, health }
}
