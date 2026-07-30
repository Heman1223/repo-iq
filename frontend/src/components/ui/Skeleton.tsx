/** Loading placeholders that match the shape of the content they replace. */

import { cx } from '@/lib/format'

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx('skeleton rounded-md', className)} aria-hidden />
}

/** Sidebar placeholder shown while repository metadata is still loading. */
export function SidebarSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading repository details">
      <div className="space-y-2">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-3 w-28" />
      </div>
      <div className="grid grid-cols-2 gap-2">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-14" />
        ))}
      </div>
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-3 w-full" />
        ))}
      </div>
    </div>
  )
}

/** Multi-line placeholder used while an answer is being generated. */
export function AnswerSkeleton() {
  return (
    <div className="space-y-2.5" role="status" aria-label="Generating answer">
      <Skeleton className="h-3 w-[92%]" />
      <Skeleton className="h-3 w-[78%]" />
      <Skeleton className="h-3 w-[85%]" />
      <Skeleton className="h-3 w-[54%]" />
    </div>
  )
}
