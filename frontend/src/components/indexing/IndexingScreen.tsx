/**
 * Full-screen pipeline progress.
 *
 * The checklist is driven by the backend's real stage, not a fake timer — each
 * row flips to "done" only once the server has moved past it.
 */

import { AnimatePresence, motion } from 'framer-motion'
import { Check, CircleDashed, Loader2, XCircle } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ErrorBanner } from '@/components/ui/ErrorBanner'
import { PIPELINE_STAGES, STAGE_ORDER } from '@/lib/constants'
import { cx } from '@/lib/format'
import type { ApiError, IndexStatus } from '@/types'

type RowState = 'done' | 'active' | 'pending'

export interface IndexingScreenProps {
  status: IndexStatus | null
  error: ApiError | null
  repoLabel: string
  onCancel: () => void
  onRetry: () => void
}

export function IndexingScreen({
  status,
  error,
  repoLabel,
  onCancel,
  onRetry,
}: IndexingScreenProps) {
  const currentRank = status ? STAGE_ORDER[status.stage] : 0
  const hasFailed = Boolean(error) || status?.stage === 'failed'
  const percent = Math.round((status?.progress ?? 0) * 100)

  const rowState = (stageRank: number): RowState => {
    if (currentRank > stageRank) return 'done'
    if (currentRank === stageRank) return 'active'
    return 'pending'
  }

  return (
    <main className="mx-auto flex min-h-[calc(100vh-3.5rem)] w-full max-w-xl flex-col justify-center px-4 py-14 sm:px-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      >
        <Card className="p-6! sm:p-7!">
          <header className="mb-6">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-faint">
              {hasFailed ? 'Indexing failed' : 'Indexing repository'}
            </p>
            <h1 className="mt-1.5 truncate font-mono text-lg tracking-tight text-ink">
              {status?.full_name || repoLabel}
            </h1>
          </header>

          {/* Progress bar */}
          <div className="mb-6">
            <div className="mb-2 flex items-baseline justify-between text-[13px]">
              <span className={cx(hasFailed ? 'text-danger' : 'text-muted')}>
                {status?.message ?? 'Starting...'}
              </span>
              <span className="font-mono text-[12px] text-faint">{percent}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-line-soft">
              <motion.div
                className={cx(
                  'h-full rounded-full',
                  hasFailed
                    ? 'bg-danger'
                    : 'bg-linear-to-r from-brand-strong via-brand to-brand-soft',
                )}
                initial={{ width: 0 }}
                animate={{ width: `${percent}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              />
            </div>
          </div>

          {/* Stage checklist */}
          <ol className="space-y-0.5" aria-label="Indexing stages">
            {PIPELINE_STAGES.map((entry) => {
              const state = hasFailed ? 'pending' : rowState(STAGE_ORDER[entry.stage])
              return (
                <li
                  key={entry.stage}
                  className={cx(
                    'flex items-center gap-2.5 rounded-lg px-2 py-2 text-[13.5px] transition-colors',
                    state === 'active' && 'bg-brand/8 text-ink',
                    state === 'done' && 'text-muted',
                    state === 'pending' && 'text-faint',
                  )}
                >
                  <StageIcon state={state} />
                  <span className={cx(state === 'active' && 'font-medium')}>{entry.label}</span>
                </li>
              )
            })}
          </ol>

          <ErrorBanner error={error} onRetry={onRetry} className="mt-6" />

          {/* Live counters, as soon as the backend knows them */}
          <AnimatePresence>
            {status?.stats && !hasFailed && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="mt-6 grid grid-cols-3 gap-2 border-t border-line-soft pt-5"
              >
                <MiniStat label="Files" value={status.stats.total_files_indexed} />
                <MiniStat label="Chunks" value={status.stats.total_chunks} />
                <MiniStat label="Vectors" value={status.stats.vector_count} />
              </motion.div>
            )}
          </AnimatePresence>

          <div className="mt-6 flex items-center justify-between gap-3 border-t border-line-soft pt-5">
            <p className="text-[12px] text-faint">
              {hasFailed
                ? 'Nothing was left behind: the clone is removed automatically.'
                : 'Embeddings run locally on this machine. First run downloads the model.'}
            </p>
            <Button variant="ghost" size="sm" onClick={onCancel}>
              {hasFailed ? 'Start over' : 'Cancel'}
            </Button>
          </div>
        </Card>
      </motion.div>
    </main>
  )
}

function StageIcon({ state }: { state: RowState }) {
  if (state === 'done') {
    return (
      <span className="inline-flex size-4 shrink-0 items-center justify-center rounded-full bg-success/15">
        <Check className="size-2.5 text-success" aria-hidden />
      </span>
    )
  }
  if (state === 'active') {
    return <Loader2 className="size-4 shrink-0 animate-spin text-brand" aria-hidden />
  }
  return <CircleDashed className="size-4 shrink-0 text-line" aria-hidden />
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-line-soft bg-surface/50 px-3 py-2">
      <p className="font-mono text-base text-ink">{value.toLocaleString('en')}</p>
      <p className="text-[11px] uppercase tracking-wider text-faint">{label}</p>
    </div>
  )
}

/** Compact inline variant used when re-indexing from inside the workspace. */
export function IndexingInlineNotice({ status }: { status: IndexStatus | null }) {
  const percent = Math.round((status?.progress ?? 0) * 100)
  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-brand/30 bg-brand/8 px-3.5 py-2.5 text-[13px] text-ink">
      <Loader2 className="size-3.5 animate-spin text-brand" aria-hidden />
      <span className="min-w-0 flex-1 truncate">{status?.message ?? 'Re-indexing...'}</span>
      <span className="font-mono text-[12px] text-muted">{percent}%</span>
    </div>
  )
}

/** Terminal-failure card for the rare case where no stage information exists. */
export function IndexingFailedNotice({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2.5 rounded-xl border border-danger/35 bg-danger/8 p-3.5">
      <XCircle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden />
      <p className="text-[13px] text-ink">{message}</p>
    </div>
  )
}
