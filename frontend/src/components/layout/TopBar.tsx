/** Application header: brand, backend status pill and repository actions. */

import { Github, Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'

import { Badge, StatusDot } from '@/components/ui/Chip'
import type { BackendState } from '@/hooks/useHealth'
import type { HealthResponse } from '@/types'

const STATE_COPY: Record<BackendState, { label: string; tone: 'neutral' | 'success' | 'warning' | 'danger' }> = {
  checking: { label: 'Connecting', tone: 'neutral' },
  online: { label: 'Backend online', tone: 'success' },
  degraded: { label: 'Gemini key missing', tone: 'warning' },
  offline: { label: 'Backend offline', tone: 'danger' },
}

export interface TopBarProps {
  backendState: BackendState
  health: HealthResponse | null
  /** Right-aligned slot for context actions (re-index, new repository, ...). */
  actions?: ReactNode
}

export function TopBar({ backendState, health, actions }: TopBarProps) {
  const { label, tone } = STATE_COPY[backendState]

  return (
    <header className="sticky top-0 z-30 border-b border-line-soft bg-canvas/80 backdrop-blur-xl">
      <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center gap-3 px-4 sm:px-6">
        <div className="flex items-center gap-2.5">
          <span className="relative flex size-8 items-center justify-center rounded-lg border border-brand/30 bg-brand/12">
            <Sparkles className="size-4 text-brand-soft" aria-hidden />
          </span>
          <div className="leading-tight">
            <p className="text-[13px] font-semibold tracking-tight text-ink">
              Repository AI Assistant
            </p>
            <p className="hidden text-[11px] text-faint sm:block">
              Understand any GitHub repository in seconds
            </p>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <Badge tone={tone} className="hidden sm:inline-flex" title={health?.llm_model ?? undefined}>
            <StatusDot tone={tone} />
            {label}
          </Badge>

          {actions}

          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer noopener"
            aria-label="GitHub"
            className="inline-flex size-9 items-center justify-center rounded-lg text-muted transition-colors hover:bg-surface-raised/70 hover:text-ink"
          >
            <Github className="size-4" aria-hidden />
          </a>
        </div>
      </div>
    </header>
  )
}
