/**
 * Markdown renderer for assistant answers.
 *
 * GFM tables/strikethrough plus highlight.js syntax colouring. Raw HTML is not
 * enabled — model output is treated as untrusted text.
 */

import { memo } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import remarkGfm from 'remark-gfm'

export interface MarkdownProps {
  content: string
}

export const Markdown = memo(function Markdown({ content }: MarkdownProps) {
  return (
    <div className="prose-answer">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={{
          // Force external links to open safely in a new tab.
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
})
