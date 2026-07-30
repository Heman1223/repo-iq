/**
 * Repository indexing state machine.
 *
 *   idle ──submit──▶ indexing ──poll──▶ ready
 *                        └──────────────▶ error
 *
 * Owns the `POST /clone` call plus the `GET /status` polling loop, and cleans up
 * its timer on unmount so a navigated-away page never keeps polling.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { cloneRepository, getIndexStatus, toApiError } from '@/lib/api'
import { STATUS_POLL_INTERVAL_MS } from '@/lib/constants'
import type { ApiError, IndexStatus } from '@/types'

export type IndexingPhase = 'idle' | 'indexing' | 'ready' | 'error'

export interface UseIndexingResult {
  phase: IndexingPhase
  status: IndexStatus | null
  error: ApiError | null
  /** True while the initial POST /clone request is in flight. */
  isSubmitting: boolean
  startIndexing: (repoUrl: string, forceReindex?: boolean) => Promise<void>
  reset: () => void
  reindex: () => Promise<void>
}

export function useIndexing(): UseIndexingResult {
  const [phase, setPhase] = useState<IndexingPhase>('idle')
  const [status, setStatus] = useState<IndexStatus | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const timerRef = useRef<number | null>(null)
  const isMountedRef = useRef(true)
  const lastUrlRef = useRef<string>('')

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      clearTimer()
    }
  }, [clearTimer])

  /** Recursive, self-scheduling poll — no interval drift, no overlapping calls. */
  const poll = useCallback(
    async (repoId: string) => {
      if (!isMountedRef.current) return

      try {
        const next = await getIndexStatus(repoId)
        if (!isMountedRef.current) return

        setStatus(next)

        if (next.stage === 'ready') {
          setPhase('ready')
          return
        }
        if (next.stage === 'failed') {
          setError({
            code: next.error_code ?? 'indexing_failed',
            message: next.error_message ?? 'Indexing failed.',
          })
          setPhase('error')
          return
        }

        timerRef.current = window.setTimeout(() => void poll(repoId), STATUS_POLL_INTERVAL_MS)
      } catch (caught) {
        if (!isMountedRef.current) return
        setError(toApiError(caught))
        setPhase('error')
      }
    },
    [],
  )

  const startIndexing = useCallback(
    async (repoUrl: string, forceReindex = false) => {
      clearTimer()
      lastUrlRef.current = repoUrl
      setError(null)
      setIsSubmitting(true)
      setPhase('indexing')
      setStatus(null)

      try {
        const response = await cloneRepository(repoUrl, forceReindex)
        if (!isMountedRef.current) return

        setStatus(response.status)

        if (response.status.stage === 'ready') {
          // Already indexed: skip straight to the workspace.
          setPhase('ready')
          return
        }
        if (response.status.stage === 'failed') {
          setError({
            code: response.status.error_code ?? 'indexing_failed',
            message: response.status.error_message ?? 'Indexing failed.',
          })
          setPhase('error')
          return
        }

        void poll(response.repo_id)
      } catch (caught) {
        if (!isMountedRef.current) return
        setError(toApiError(caught))
        setPhase('error')
      } finally {
        if (isMountedRef.current) setIsSubmitting(false)
      }
    },
    [clearTimer, poll],
  )

  const reindex = useCallback(async () => {
    const url = status?.html_url ?? lastUrlRef.current
    if (url) await startIndexing(url, true)
  }, [startIndexing, status])

  const reset = useCallback(() => {
    clearTimer()
    setPhase('idle')
    setStatus(null)
    setError(null)
    setIsSubmitting(false)
  }, [clearTimer])

  return { phase, status, error, isSubmitting, startIndexing, reset, reindex }
}
