/**
 * Source files panel shown beneath every grounded answer.
 *
 * This is the trust mechanism of the whole product: each citation names the file,
 * its line range, a relevance score and an expandable snippet of the exact text
 * that was retrieved.
 */

import { AnimatePresence, motion } from 'framer-motion'
import { ChevronRight, FileCode2, Quote } from 'lucide-react'
import { useState } from 'react'

import { cx, directoryName, fileName } from '@/lib/format'
import type { SourceReference } from '@/types'

export interface SourceCitationsProps {
  sources: SourceReference[]
  /** GitHub URL + branch let each citation deep-link to the real file. */
  repoUrl?: string
  defaultBranch?: string
}

export function SourceCitations({ sources, repoUrl, defaultBranch = 'main' }: SourceCitationsProps) {
  const [expanded, setExpanded] = useState<string | null>(null)

  if (sources.length === 0) return null

  const githubLink = (source: SourceReference): string | undefined => {
    if (!repoUrl) return undefined
    const lines = source.start_line ? `#L${source.start_line}-L${source.end_line ?? source.start_line}` : ''
    return `${repoUrl}/blob/${defaultBranch}/${source.file_path}${lines}`
  }

  return (
    <div className="mt-3.5 border-t border-line-soft pt-3">
      <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
        <Quote className="size-3" aria-hidden />
        Source files
        <span className="font-mono lowercase tracking-normal">({sources.length})</span>
      </p>

      <ul className="space-y-1">
        {sources.map((source) => {
          const key = `${source.file_path}:${source.chunk_index}`
          const isOpen = expanded === key
          const href = githubLink(source)

          return (
            <li key={key}>
              <div
                className={cx(
                  'overflow-hidden rounded-lg border transition-colors',
                  isOpen
                    ? 'border-brand/35 bg-brand/6'
                    : 'border-line-soft bg-surface/40 hover:border-line',
                )}
              >
                <button
                  type="button"
                  onClick={() => setExpanded(isOpen ? null : key)}
                  aria-expanded={isOpen}
                  className="flex w-full items-center gap-2 px-2.5 py-2 text-left"
                >
                  <ChevronRight
                    className={cx(
                      'size-3.5 shrink-0 text-faint transition-transform duration-200',
                      isOpen && 'rotate-90',
                    )}
                    aria-hidden
                  />
                  <FileCode2 className="size-3.5 shrink-0 text-brand/70" aria-hidden />

                  <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-ink">
                    {fileName(source.file_path)}
                    {directoryName(source.file_path) && (
                      <span className="text-faint"> · {directoryName(source.file_path)}</span>
                    )}
                  </span>

                  {source.start_line ? (
                    <span className="shrink-0 font-mono text-[11px] text-faint">
                      L{source.start_line}–{source.end_line}
                    </span>
                  ) : null}

                  <span
                    className="shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] text-brand-soft"
                    title="Semantic relevance"
                  >
                    {(source.relevance * 100).toFixed(0)}%
                  </span>
                </button>

                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                    >
                      <div className="border-t border-line-soft/70 px-2.5 py-2.5">
                        <pre className="max-h-56 overflow-auto rounded-md bg-canvas-inset p-2.5 text-[11.5px] leading-relaxed text-muted">
                          <code>{source.snippet}</code>
                        </pre>
                        {href && (
                          <a
                            href={href}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="mt-2 inline-block font-mono text-[11px] text-brand-soft hover:underline"
                          >
                            View on GitHub ↗
                          </a>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
