/** Small, pure formatting helpers shared by the dashboard and chat. */

/** `1234` -> `1.2k`, `1234567` -> `1.2M`. */
export function formatCompactNumber(value: number): string {
  if (!Number.isFinite(value)) return '0'
  if (Math.abs(value) < 1000) return String(value)
  return new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}

/** `1234` -> `1,234`. */
export function formatNumber(value: number): string {
  return new Intl.NumberFormat('en').format(Number.isFinite(value) ? value : 0)
}

/** GitHub reports repository size in kilobytes. */
export function formatKilobytes(sizeKb: number): string {
  if (sizeKb <= 0) return '—'
  if (sizeKb < 1024) return `${Math.round(sizeKb)} KB`
  if (sizeKb < 1024 * 1024) return `${(sizeKb / 1024).toFixed(1)} MB`
  return `${(sizeKb / (1024 * 1024)).toFixed(1)} GB`
}

/** `0.42` -> `420 ms`, `12.5` -> `12.5s`, `95` -> `1m 35s`. */
export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return '—'
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const minutes = Math.floor(seconds / 60)
  return `${minutes}m ${Math.round(seconds % 60)}s`
}

export function formatMilliseconds(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)}s`
}

/** "3 days ago" style label for ISO timestamps; `—` when absent. */
export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const timestamp = new Date(iso).getTime()
  if (Number.isNaN(timestamp)) return '—'

  const deltaSeconds = (timestamp - Date.now()) / 1000
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['year', 31_536_000],
    ['month', 2_592_000],
    ['week', 604_800],
    ['day', 86_400],
    ['hour', 3_600],
    ['minute', 60],
  ]
  const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

  for (const [unit, secondsInUnit] of units) {
    if (Math.abs(deltaSeconds) >= secondsInUnit) {
      return formatter.format(Math.round(deltaSeconds / secondsInUnit), unit)
    }
  }
  return 'just now'
}

/** `src/services/auth/token.ts` -> `token.ts`. */
export function fileName(path: string): string {
  return path.split('/').pop() ?? path
}

/** `src/services/auth/token.ts` -> `src/services/auth`. */
export function directoryName(path: string): string {
  const parts = path.split('/')
  parts.pop()
  return parts.join('/')
}

/** Collapse long paths for narrow sidebars: `src/.../auth/token.ts`. */
export function truncatePath(path: string, maxSegments = 4): string {
  const parts = path.split('/')
  if (parts.length <= maxSegments) return path
  return [parts[0], '…', ...parts.slice(-(maxSegments - 1))].join('/')
}

/** Tailwind-friendly conditional class joiner (avoids a clsx dependency). */
export function cx(...values: (string | false | null | undefined)[]): string {
  return values.filter(Boolean).join(' ')
}
