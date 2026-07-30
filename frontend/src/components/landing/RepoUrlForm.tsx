/**
 * Hero input: validates a GitHub URL client-side before hitting the backend,
 * so obvious mistakes get instant feedback.
 */

import { motion } from 'framer-motion'
import { ArrowRight, Github, Search } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/Button'
import { SAMPLE_REPOSITORIES } from '@/lib/constants'
import { cx } from '@/lib/format'

/** Mirrors the backend's accepted forms (see `utils/repo_url.py`). */
const GITHUB_URL_PATTERN =
  /^(?:https?:\/\/)?(?:www\.)?github\.com\/[A-Za-z0-9][A-Za-z0-9._-]*\/[A-Za-z0-9][A-Za-z0-9._-]*(?:\.git)?(?:\/.*)?$/

export interface RepoUrlFormProps {
  onSubmit: (repoUrl: string) => void
  isBusy?: boolean
  /** Pre-fills the field so a failed attempt does not have to be retyped. */
  initialValue?: string
}

export function RepoUrlForm({ onSubmit, isBusy = false, initialValue = '' }: RepoUrlFormProps) {
  const [value, setValue] = useState(initialValue)
  const [localError, setLocalError] = useState<string | null>(null)
  const [isFocused, setIsFocused] = useState(false)

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    const trimmed = value.trim()

    if (!trimmed) {
      setLocalError('Paste a GitHub repository URL to get started.')
      return
    }
    if (!GITHUB_URL_PATTERN.test(trimmed)) {
      setLocalError('That does not look like a GitHub repository URL.')
      return
    }

    setLocalError(null)
    onSubmit(trimmed)
  }

  return (
    <div className="w-full max-w-2xl">
      <form onSubmit={handleSubmit} noValidate>
        <motion.div
          animate={{
            boxShadow: isFocused
              ? '0 0 0 1px rgba(59,130,246,0.55), 0 18px 50px -24px rgba(59,130,246,0.65)'
              : '0 0 0 1px rgba(48,54,61,1), 0 12px 34px -22px rgba(1,4,9,0.9)',
          }}
          transition={{ duration: 0.25 }}
          className="flex flex-col gap-2 rounded-2xl bg-surface/70 p-2 backdrop-blur-md sm:flex-row sm:items-center"
        >
          <div className="flex min-w-0 flex-1 items-center gap-2.5 px-3">
            <Github className="size-4 shrink-0 text-faint" aria-hidden />
            <input
              type="url"
              value={value}
              onChange={(event) => {
                setValue(event.target.value)
                if (localError) setLocalError(null)
              }}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              placeholder="https://github.com/owner/repository"
              spellCheck={false}
              autoComplete="off"
              aria-label="GitHub repository URL"
              aria-invalid={Boolean(localError)}
              disabled={isBusy}
              className={cx(
                'h-11 w-full min-w-0 bg-transparent text-[15px] text-ink outline-none',
                'placeholder:text-faint disabled:opacity-60',
              )}
            />
          </div>

          <Button
            type="submit"
            size="lg"
            isLoading={isBusy}
            rightIcon={<ArrowRight className="size-4" />}
            className="w-full shrink-0 sm:w-auto"
          >
            {isBusy ? 'Indexing' : 'Index repository'}
          </Button>
        </motion.div>
      </form>

      <div className="mt-3 flex min-h-6 flex-wrap items-center gap-x-2 gap-y-1.5 text-[13px]">
        {localError ? (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-danger"
          >
            {localError}
          </motion.p>
        ) : (
          <>
            <span className="inline-flex items-center gap-1.5 text-faint">
              <Search className="size-3.5" aria-hidden />
              Try
            </span>
            {SAMPLE_REPOSITORIES.map((sample) => (
              <button
                key={sample.url}
                type="button"
                disabled={isBusy}
                onClick={() => {
                  setValue(sample.url)
                  setLocalError(null)
                }}
                className="rounded-md px-1.5 py-0.5 font-mono text-[12px] text-muted transition-colors hover:bg-brand/10 hover:text-brand-soft disabled:opacity-50"
              >
                {sample.label}
              </button>
            ))}
          </>
        )}
      </div>
    </div>
  )
}
