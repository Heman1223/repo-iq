/**
 * Repository dashboard.
 *
 * Everything a developer wants before asking a question: GitHub facts, index
 * statistics, language mix and the top-level layout of the repository.
 */

import {
  Boxes,
  Calendar,
  Clock,
  Cpu,
  ExternalLink,
  Files,
  FolderTree,
  GitBranch,
  GitFork,
  Info,
  Layers,
  Scale,
  Star,
  Trash2,
  type LucideIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'

import { Card, Section } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Chip'
import { SidebarSkeleton } from '@/components/ui/Skeleton'
import {
  formatCompactNumber,
  formatDuration,
  formatKilobytes,
  formatNumber,
  formatRelativeTime,
} from '@/lib/format'
import type { IndexStatus } from '@/types'

export interface RepositorySidebarProps {
  status: IndexStatus | null
  onDelete?: () => void
}

export function RepositorySidebar({ status, onDelete }: RepositorySidebarProps) {
  if (!status?.metadata || !status.stats) {
    return (
      <Card className="h-full overflow-y-auto" role="region" aria-label="Repository details">
        <SidebarSkeleton />
      </Card>
    )
  }

  const { metadata, stats } = status
  const languageEntries = Object.entries(stats.languages).slice(0, 6)
  const languageTotal = Object.values(stats.languages).reduce((sum, count) => sum + count, 0) || 1

  return (
    <Card
      className="flex h-full flex-col gap-6 overflow-y-auto p-5!"
      role="region"
      aria-label="Repository details"
    >
      {/* ------------------------------------------------------------ identity */}
      <header>
        <p className="text-[11px] font-medium text-faint">{metadata.owner}</p>
        <div className="flex items-start justify-between gap-2">
          <h2 className="min-w-0 wrap-break-word text-lg font-semibold tracking-tight text-ink">
            {metadata.name}
          </h2>
          <a
            href={metadata.html_url}
            target="_blank"
            rel="noreferrer noopener"
            aria-label="Open on GitHub"
            className="mt-1 shrink-0 text-faint transition-colors hover:text-brand-soft"
          >
            <ExternalLink className="size-3.5" aria-hidden />
          </a>
        </div>

        {metadata.description && (
          <p className="mt-2 text-[13px] leading-relaxed text-muted">{metadata.description}</p>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          {metadata.language && <Badge tone="brand">{metadata.language}</Badge>}
          <Badge>
            <GitBranch className="size-3" aria-hidden />
            {metadata.default_branch}
          </Badge>
          {metadata.license_name && metadata.license_name !== 'NOASSERTION' && (
            <Badge>
              <Scale className="size-3" aria-hidden />
              {metadata.license_name}
            </Badge>
          )}
          {metadata.is_fork && <Badge tone="warning">fork</Badge>}
        </div>

        {metadata.topics.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1">
            {metadata.topics.slice(0, 6).map((topic) => (
              <span
                key={topic}
                className="rounded-md bg-surface-raised/70 px-1.5 py-0.5 text-[11px] text-faint"
              >
                {topic}
              </span>
            ))}
          </div>
        )}
      </header>

      {/* -------------------------------------------------------- github stats */}
      <Section title="Repository" icon={<Info className="size-3" aria-hidden />}>
        <div className="grid grid-cols-2 gap-2">
          <Stat icon={Star} label="Stars" value={formatCompactNumber(metadata.stars)} />
          <Stat icon={GitFork} label="Forks" value={formatCompactNumber(metadata.forks)} />
          <Stat icon={Boxes} label="Size" value={formatKilobytes(metadata.size_kb)} />
          <Stat
            icon={Calendar}
            label="Updated"
            value={formatRelativeTime(metadata.pushed_at ?? metadata.updated_at)}
          />
        </div>
      </Section>

      {/* --------------------------------------------------------- index stats */}
      <Section title="Index" icon={<Layers className="size-3" aria-hidden />}>
        <div className="grid grid-cols-2 gap-2">
          <Stat icon={Files} label="Files indexed" value={formatNumber(stats.total_files_indexed)} />
          <Stat icon={Layers} label="Chunks" value={formatNumber(stats.total_chunks)} />
          <Stat icon={Cpu} label="Vectors" value={formatNumber(stats.vector_count)} />
          <Stat icon={Clock} label="Index time" value={formatDuration(stats.indexing_seconds)} />
        </div>

        <div className="space-y-1.5 rounded-lg border border-line-soft bg-surface/40 px-3 py-2.5 text-[12px]">
          <Row label="Embedding status">
            <Badge tone="success">ready</Badge>
          </Row>
          <Row label="Model">
            <span
              className="truncate font-mono text-[11px] text-muted"
              title={stats.embedding_model}
            >
              {stats.embedding_model.split('/').pop()}
            </span>
          </Row>
          <Row label="Dimensions">
            <span className="font-mono text-[11px] text-muted">{stats.embedding_dimensions}</span>
          </Row>
          <Row label="Files skipped">
            <span className="font-mono text-[11px] text-muted">
              {formatNumber(stats.total_files_skipped)}
            </span>
          </Row>
          <Row label="Indexed">
            <span className="text-[11px] text-muted">{formatRelativeTime(stats.indexed_at)}</span>
          </Row>
        </div>
      </Section>

      {/* ------------------------------------------------------------ languages */}
      {languageEntries.length > 0 && (
        <Section title="Languages" icon={<Cpu className="size-3" aria-hidden />}>
          <div className="space-y-2">
            {languageEntries.map(([language, count]) => (
              <div key={language} className="space-y-1">
                <div className="flex items-baseline justify-between text-[12px]">
                  <span className="text-muted">{language}</span>
                  <span className="font-mono text-[11px] text-faint">{count}</span>
                </div>
                <div className="h-1 overflow-hidden rounded-full bg-line-soft">
                  <div
                    className="h-full rounded-full bg-brand/70"
                    style={{ width: `${Math.max((count / languageTotal) * 100, 2)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* -------------------------------------------------------------- layout */}
      {stats.top_level_entries.length > 0 && (
        <Section title="Structure" icon={<FolderTree className="size-3" aria-hidden />}>
          <ul className="space-y-0.5 font-mono text-[12px]">
            {stats.top_level_entries.slice(0, 14).map((entry) => (
              <li key={entry} className={entry.endsWith('/') ? 'text-brand-soft/85' : 'text-muted'}>
                {entry}
              </li>
            ))}
            {stats.top_level_entries.length > 14 && (
              <li className="text-faint">+{stats.top_level_entries.length - 14} more</li>
            )}
          </ul>
        </Section>
      )}

      {onDelete && (
        <button
          type="button"
          onClick={onDelete}
          className="mt-auto inline-flex items-center gap-2 self-start rounded-lg px-2 py-1.5 text-[12px] text-faint transition-colors hover:bg-danger/10 hover:text-danger"
        >
          <Trash2 className="size-3.5" aria-hidden />
          Delete index
        </button>
      )}
    </Card>
  )
}

function Stat({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line-soft bg-surface/40 px-3 py-2.5">
      <p className="flex items-center gap-1.5 text-[11px] text-faint">
        <Icon className="size-3" aria-hidden />
        {label}
      </p>
      <p className="mt-0.5 truncate text-[15px] font-medium text-ink" title={value}>
        {value}
      </p>
    </div>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-faint">{label}</span>
      {children}
    </div>
  )
}
