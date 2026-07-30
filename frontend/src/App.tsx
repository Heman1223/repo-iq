/**
 * Application shell.
 *
 * Routes between the three views without a router — the app has exactly one
 * linear flow:  landing → indexing → workspace.
 */

import { AnimatePresence, motion } from 'framer-motion'
import { Plus, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { IndexingScreen } from '@/components/indexing/IndexingScreen'
import { LandingPage } from '@/components/landing/LandingPage'
import { TopBar } from '@/components/layout/TopBar'
import { Workspace } from '@/components/workspace/Workspace'
import { Button } from '@/components/ui/Button'
import { useHealth } from '@/hooks/useHealth'
import { useIndexing } from '@/hooks/useIndexing'
import { deleteRepository, listRepositories } from '@/lib/api'
import type { IndexedRepositorySummary } from '@/types'

export default function App() {
  const { state: backendState, health } = useHealth()
  const indexing = useIndexing()
  const [recentRepositories, setRecentRepositories] = useState<IndexedRepositorySummary[]>([])
  const [lastRepoUrl, setLastRepoUrl] = useState('')

  /** Repositories already indexed on this server, offered on the landing page. */
  const refreshRecent = useCallback(() => {
    listRepositories()
      .then(setRecentRepositories)
      .catch(() => setRecentRepositories([]))
  }, [])

  useEffect(() => {
    if (backendState === 'online' || backendState === 'degraded') refreshRecent()
  }, [backendState, refreshRecent])

  const handleSubmit = useCallback(
    (repoUrl: string) => {
      setLastRepoUrl(repoUrl)
      void indexing.startIndexing(repoUrl)
    },
    [indexing],
  )

  const handleOpenRecent = useCallback(
    (repository: IndexedRepositorySummary) => {
      setLastRepoUrl(repository.html_url)
      void indexing.startIndexing(repository.html_url)
    },
    [indexing],
  )

  /** Full reset: back to an empty landing page. */
  const handleReset = useCallback(() => {
    indexing.reset()
    setLastRepoUrl('')
    refreshRecent()
  }, [indexing, refreshRecent])

  /** Clears the error but keeps the typed URL so it can be corrected. */
  const handleDismissError = useCallback(() => {
    indexing.reset()
  }, [indexing])

  const handleDeleteIndex = useCallback(async () => {
    const repoId = indexing.status?.repo_id
    if (!repoId) return
    try {
      await deleteRepository(repoId)
    } finally {
      handleReset()
    }
  }, [handleReset, indexing.status])

  const isReady = indexing.phase === 'ready' && indexing.status?.is_ready
  const canAsk = backendState !== 'offline' && Boolean(health?.llm_configured)

  // A failure with no status never got as far as a job (bad URL, 404, offline
  // backend), so it belongs on the landing page rather than the progress screen.
  const showProgressScreen =
    indexing.phase === 'indexing' || (indexing.phase === 'error' && indexing.status !== null)

  return (
    <div className="min-h-screen">
      <TopBar
        backendState={backendState}
        health={health}
        actions={
          isReady && (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void indexing.reindex()}
                leftIcon={<RefreshCw className="size-3.5" />}
              >
                <span className="hidden sm:inline">Re-index</span>
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleReset}
                leftIcon={<Plus className="size-3.5" />}
              >
                <span className="hidden sm:inline">New repository</span>
              </Button>
            </>
          )
        }
      />

      <AnimatePresence mode="wait">
        {isReady && indexing.status ? (
          <motion.div
            key="workspace"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <Workspace
              status={indexing.status}
              canAsk={canAsk}
              askDisabledReason={
                backendState === 'offline'
                  ? 'The backend is offline — start the FastAPI server to ask questions.'
                  : 'Set GEMINI_API_KEY in backend/.env to enable answers.'
              }
              onDeleteIndex={() => void handleDeleteIndex()}
            />
          </motion.div>
        ) : showProgressScreen ? (
          <motion.div
            key="indexing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <IndexingScreen
              status={indexing.status}
              error={indexing.error}
              repoLabel={indexing.status?.full_name ?? 'repository'}
              onCancel={handleReset}
              onRetry={() => void indexing.reindex()}
            />
          </motion.div>
        ) : (
          <motion.div
            key="landing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <LandingPage
              onSubmit={handleSubmit}
              isBusy={indexing.isSubmitting}
              error={indexing.error}
              onDismissError={handleDismissError}
              recentRepositories={recentRepositories}
              onOpenRecent={handleOpenRecent}
              lastRepoUrl={lastRepoUrl}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
