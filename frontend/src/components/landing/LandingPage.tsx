/** Landing page: hero, URL input, example questions, feature grid, pipeline strip. */

import { motion } from 'framer-motion'
import { ArrowUpRight, MessageSquareCode, Sparkles } from 'lucide-react'

import { FeatureGrid } from '@/components/landing/FeatureGrid'
import { RepoUrlForm } from '@/components/landing/RepoUrlForm'
import { Card, FadeIn } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Chip'
import { ErrorBanner } from '@/components/ui/ErrorBanner'
import { EXAMPLE_QUESTIONS } from '@/lib/constants'
import type { ApiError, IndexedRepositorySummary } from '@/types'

/** The pipeline, stated plainly - this is the project's core value proposition. */
const PIPELINE_STEPS = [
  'Clone',
  'Filter files',
  'Chunk',
  'Embed locally',
  'ChromaDB',
  'Retrieve',
  'Gemini',
] as const

export interface LandingPageProps {
  onSubmit: (repoUrl: string) => void
  isBusy: boolean
  error: ApiError | null
  onDismissError: () => void
  recentRepositories: IndexedRepositorySummary[]
  onOpenRecent: (repository: IndexedRepositorySummary) => void
  /** Last submitted URL, restored after a failed attempt. */
  lastRepoUrl?: string
}

export function LandingPage({
  onSubmit,
  isBusy,
  error,
  onDismissError,
  recentRepositories,
  onOpenRecent,
  lastRepoUrl,
}: LandingPageProps) {
  return (
    <main className="mx-auto w-full max-w-6xl px-4 pb-24 pt-14 sm:px-6 sm:pt-20">
      {/* ------------------------------------------------------------- hero */}
      <section className="flex flex-col items-center text-center">
        <FadeIn>
          <Badge tone="brand" className="mb-6">
            <Sparkles className="size-3" aria-hidden />
            Retrieval-Augmented Generation over real code
          </Badge>
        </FadeIn>

        <FadeIn delay={0.05}>
          <h1 className="max-w-3xl text-balance text-4xl font-semibold leading-[1.08] tracking-[-0.03em] text-ink sm:text-6xl">
            Understand any GitHub repository in{' '}
            <span className="bg-linear-to-r from-brand-soft via-brand to-brand-strong bg-clip-text text-transparent">
              seconds
            </span>
          </h1>
        </FadeIn>

        <FadeIn delay={0.1}>
          <p className="mt-5 max-w-xl text-pretty text-[15px] leading-relaxed text-muted sm:text-base">
            Paste a repository URL. The assistant indexes the codebase with local embeddings,
            then answers your questions with citations to the exact files the answer came from.
          </p>
        </FadeIn>

        <FadeIn delay={0.16} className="mt-9 flex w-full justify-center">
          <RepoUrlForm onSubmit={onSubmit} isBusy={isBusy} initialValue={lastRepoUrl} />
        </FadeIn>

        <ErrorBanner
          error={error}
          onDismiss={onDismissError}
          className="mt-5 w-full max-w-2xl text-left"
        />

        {/* Pipeline strip - makes the architecture legible at a glance. */}
        <FadeIn delay={0.22} className="mt-10 w-full">
          <div className="flex flex-wrap items-center justify-center gap-x-1.5 gap-y-2 text-[11px] font-medium uppercase tracking-[0.1em] text-faint">
            {PIPELINE_STEPS.map((step, index) => (
              <span key={step} className="flex items-center gap-1.5">
                <span className="rounded-md border border-line-soft bg-surface/50 px-2 py-1">
                  {step}
                </span>
                {index < PIPELINE_STEPS.length - 1 && <span aria-hidden>&rarr;</span>}
              </span>
            ))}
          </div>
        </FadeIn>
      </section>

      {/* -------------------------------------------- previously indexed repos */}
      {recentRepositories.length > 0 && (
        <FadeIn delay={0.1} className="mt-14">
          <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-faint">
            Already indexed on this server
          </h2>
          <div className="flex flex-wrap gap-2">
            {recentRepositories.map((repository) => (
              <button
                key={repository.repo_id}
                type="button"
                onClick={() => onOpenRecent(repository)}
                className="group inline-flex items-center gap-2 rounded-xl border border-line-soft bg-surface/60 px-3 py-2 text-[13px] text-muted backdrop-blur-sm transition-colors hover:border-brand/40 hover:bg-brand/10 hover:text-ink"
              >
                <MessageSquareCode className="size-3.5 text-faint group-hover:text-brand-soft" aria-hidden />
                <span className="font-mono text-[12px]">{repository.full_name}</span>
                <span className="text-faint">{repository.total_chunks} chunks</span>
                <ArrowUpRight className="size-3.5 opacity-0 transition-opacity group-hover:opacity-100" aria-hidden />
              </button>
            ))}
          </div>
        </FadeIn>
      )}

      {/* --------------------------------------------------- example questions */}
      <section className="mt-16">
        <FadeIn>
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-faint">
            Ask questions like
          </h2>
        </FadeIn>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {EXAMPLE_QUESTIONS.map((question, index) => (
            <motion.div
              key={question}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.4, delay: index * 0.05 }}
            >
              <Card tone="subtle" className="h-full p-4!">
                <p className="flex items-start gap-2.5 text-[13.5px] leading-relaxed text-muted">
                  <MessageSquareCode className="mt-0.5 size-4 shrink-0 text-brand/70" aria-hidden />
                  {question}
                </p>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------------------ features */}
      <section className="mt-16">
        <FadeIn>
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-faint">
            How it works
          </h2>
        </FadeIn>
        <div className="mt-4">
          <FeatureGrid />
        </div>
      </section>

      <footer className="mt-20 border-t border-line-soft pt-6 text-center text-[12px] text-faint">
        FastAPI &middot; LangChain &middot; ChromaDB &middot; all-MiniLM-L6-v2 &middot; Google Gemini
        &middot; React &middot; TailwindCSS
      </footer>
    </main>
  )
}
