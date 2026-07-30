/** Inline, dismissible error surface with per-error-code guidance. */

import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, RefreshCw, X } from 'lucide-react'

import { Button, IconButton } from '@/components/ui/Button'
import type { ApiError } from '@/types'

/**
 * Actionable next step for each backend error code. Generic messages are the
 * enemy of a good developer tool — every failure gets a concrete suggestion.
 */
const REMEDIES: Record<string, string> = {
  invalid_repository_url: 'Use the form https://github.com/<owner>/<repository>.',
  repository_not_found: 'Double-check the spelling, or confirm the repository still exists.',
  private_repository: 'Only public repositories can be indexed right now.',
  empty_repository: 'Try a repository that contains source files.',
  unsupported_repository: 'This repository exceeds the configured size limits.',
  clone_failed: 'Check your network connection and try again.',
  github_api_error: 'Add a GITHUB_TOKEN to backend/.env to raise the rate limit.',
  llm_not_configured: 'Set GEMINI_API_KEY in backend/.env and restart the backend.',
  llm_error: 'Wait a moment and retry — this is usually a rate limit.',
  embedding_failed: 'The embedding model failed to load. Check the backend logs.',
  repository_not_indexed: 'Index the repository again to rebuild its vectors.',
  indexing_in_progress: 'Indexing is still running — this will resolve shortly.',
  network_error: 'Start the backend with: uvicorn app.main:app --reload --port 8000',
  timeout: 'Large repositories take longer. Retry, or pick a smaller repository.',
}

export interface ErrorBannerProps {
  error: ApiError | null
  onDismiss?: () => void
  onRetry?: () => void
  className?: string
}

export function ErrorBanner({ error, onDismiss, onRetry, className }: ErrorBannerProps) {
  return (
    <AnimatePresence>
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -6, height: 0 }}
          animate={{ opacity: 1, y: 0, height: 'auto' }}
          exit={{ opacity: 0, y: -6, height: 0 }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className={className}
        >
          <div
            role="alert"
            className="flex items-start gap-3 rounded-xl border border-danger/35 bg-danger/8 p-3.5 backdrop-blur-sm"
          >
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden />

            <div className="min-w-0 flex-1 space-y-1">
              <p className="text-sm font-medium text-ink">{error.message}</p>
              {(REMEDIES[error.code] ?? error.hint) && (
                <p className="text-[13px] leading-relaxed text-muted">
                  {REMEDIES[error.code] ?? error.hint}
                </p>
              )}
              {onRetry && (
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-2"
                  onClick={onRetry}
                  leftIcon={<RefreshCw className="size-3.5" />}
                >
                  Try again
                </Button>
              )}
            </div>

            {onDismiss && (
              <IconButton label="Dismiss error" onClick={onDismiss} className="size-7 shrink-0">
                <X className="size-3.5" />
              </IconButton>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
