/** Feature cards explaining the RAG pipeline behind the product. */

import { motion } from 'framer-motion'
import {
  Database,
  FileCode2,
  GitBranch,
  Layers,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from 'lucide-react'

import { Card } from '@/components/ui/Card'
import { FEATURES, type FeatureCopy } from '@/lib/constants'

/** Icon registry so copy can stay a plain, serialisable constant. */
const ICONS: Record<FeatureCopy['icon'], LucideIcon> = {
  GitBranch,
  Layers,
  Database,
  Sparkles,
  FileCode2,
  ShieldCheck,
}

export function FeatureGrid() {
  return (
    <div className="grid w-full gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {FEATURES.map((feature, index) => {
        const Icon = ICONS[feature.icon]
        return (
          <motion.div
            key={feature.title}
            initial={{ opacity: 0, y: 14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.45, delay: index * 0.06, ease: [0.22, 1, 0.36, 1] }}
          >
            <Card interactive className="h-full">
              <span className="mb-4 inline-flex size-9 items-center justify-center rounded-lg border border-brand/25 bg-brand/10">
                <Icon className="size-4 text-brand-soft" aria-hidden />
              </span>
              <h3 className="text-[15px] font-semibold tracking-tight text-ink">{feature.title}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{feature.body}</p>
            </Card>
          </motion.div>
        )
      })}
    </div>
  )
}
