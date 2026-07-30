/** Static UI content: suggestions, landing copy and pipeline stage metadata. */

import type { IndexStage } from '@/types'

/** Chips shown above the prompt box inside the workspace. */
export const SUGGESTED_QUESTIONS: readonly string[] = [
  'Explain this project',
  'Explain the folder structure',
  'What technologies are used?',
  'How does authentication work?',
  'Which file handles API routing?',
  'Where is the database connection created?',
  'Which dependencies are important?',
  'Generate onboarding instructions for a new developer',
]

/** Longer, more evocative prompts shown on the landing page. */
export const EXAMPLE_QUESTIONS: readonly string[] = [
  'Where is the JWT generated?',
  'Explain how the backend communicates with the frontend',
  'Which files contain authentication middleware?',
  'How is user registration implemented?',
  'Summarize this repository',
]

/** Public repositories that are safe, small and quick to demo with. */
export const SAMPLE_REPOSITORIES: readonly { label: string; url: string }[] = [
  { label: 'tiangolo/fastapi', url: 'https://github.com/tiangolo/fastapi' },
  { label: 'pallets/flask', url: 'https://github.com/pallets/flask' },
  { label: 'axios/axios', url: 'https://github.com/axios/axios' },
]

export interface FeatureCopy {
  /** Lucide icon name, resolved in `FeatureGrid`. */
  icon: 'GitBranch' | 'Layers' | 'Database' | 'Sparkles' | 'FileCode2' | 'ShieldCheck'
  title: string
  body: string
}

export const FEATURES: readonly FeatureCopy[] = [
  {
    icon: 'GitBranch',
    title: 'Clone & scan',
    body: 'Shallow-clones any public repository, then keeps only the source files worth reading — no node_modules, no lockfiles, no binaries.',
  },
  {
    icon: 'Layers',
    title: 'Code-aware chunking',
    body: 'LangChain splitters cut along class and function boundaries with overlap, so retrieved context never ends mid-thought.',
  },
  {
    icon: 'Database',
    title: 'Local embeddings',
    body: 'all-MiniLM-L6-v2 runs on your machine and vectors persist in ChromaDB. Zero embedding cost, instant re-use.',
  },
  {
    icon: 'Sparkles',
    title: 'Grounded answers',
    body: 'Only the retrieved chunks reach Gemini. If the repository does not contain the answer, the assistant says so.',
  },
  {
    icon: 'FileCode2',
    title: 'Real citations',
    body: 'Every response lists the exact files and line ranges it came from, with snippets you can expand inline.',
  },
  {
    icon: 'ShieldCheck',
    title: 'Read-only by design',
    body: 'Repository code is never executed. Paths are sanitised, symlinks refused and traversal blocked before any read.',
  },
]

/** Ordered stage list for the loading screen checklist. */
export const PIPELINE_STAGES: readonly { stage: IndexStage; label: string }[] = [
  { stage: 'validating', label: 'Validating repository' },
  { stage: 'cloning', label: 'Cloning repository' },
  { stage: 'reading_files', label: 'Reading files' },
  { stage: 'chunking', label: 'Splitting into chunks' },
  { stage: 'embedding', label: 'Generating embeddings' },
  { stage: 'storing', label: 'Creating vector database' },
  { stage: 'finalizing', label: 'Almost ready' },
]

/** Rank used to decide whether a stage is done, active or pending. */
export const STAGE_ORDER: Record<IndexStage, number> = {
  queued: 0,
  validating: 1,
  cloning: 2,
  reading_files: 3,
  chunking: 4,
  embedding: 5,
  storing: 6,
  finalizing: 7,
  ready: 8,
  failed: 9,
}

/** How often `GET /status` is polled while a job is running. */
export const STATUS_POLL_INTERVAL_MS = 900

/** Max characters accepted by the prompt box (mirrors the backend limit). */
export const MAX_QUESTION_LENGTH = 2000
