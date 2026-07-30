/**
 * Module 1 — Landing Page (TC_UI_001 … TC_UI_005)
 * Module 2 — client-side URL validation (TC_REPO_002 … TC_REPO_008)
 */

import { expect, test } from '@playwright/test'

import { DEGRADED, mockApi } from './support/mockApi'

test.beforeEach(async ({ page }) => {
  await mockApi(page)
  await page.goto('/')
})

test.describe('Module 1 — Landing page', () => {
  test('TC_UI_001 — application loads successfully', async ({ page }) => {
    await expect(page).toHaveTitle(/GitHub Repository AI Assistant/)
    await expect(
      page.getByRole('heading', { name: /Understand any GitHub repository in/i }),
    ).toBeVisible()
    await expect(page.getByText('Repository AI Assistant').first()).toBeVisible()

    // No console errors while rendering.
    const errors: string[] = []
    page.on('console', (message) => message.type() === 'error' && errors.push(message.text()))
    await page.waitForTimeout(400)
    expect(errors).toEqual([])
  })

  test('TC_UI_002 — URL input is visible and editable', async ({ page }) => {
    const input = page.getByLabel('GitHub repository URL')

    await expect(input).toBeVisible()
    await expect(input).toBeEnabled()
    await expect(input).toHaveAttribute('placeholder', 'https://github.com/owner/repository')

    await input.fill('https://github.com/pallets/flask')
    await expect(input).toHaveValue('https://github.com/pallets/flask')
  })

  test('TC_UI_003 — "Index repository" button is visible and clickable', async ({ page }) => {
    const button = page.getByRole('button', { name: /index repository/i })
    await expect(button).toBeVisible()
    await expect(button).toBeEnabled()

    await page.getByLabel('GitHub repository URL').fill('https://github.com/pallets/flask')
    await button.click()
    // Clicking navigates away from the landing page.
    await expect(page.getByRole('textbox', { name: 'Question' })).toBeVisible()
  })

  test('TC_UI_005 — dark GitHub-inspired blue theme is applied', async ({ page }) => {
    // Canvas #0D1117
    await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(13, 17, 23)')

    // Primary text #F8FAFC
    await expect(page.locator('body')).toHaveCSS('color', 'rgb(248, 250, 252)')

    // Accent is blue, not green: the primary button uses #3B82F6.
    await expect(page.getByRole('button', { name: /index repository/i })).toHaveCSS(
      'background-color',
      'rgb(59, 130, 246)',
    )

    // Cards are the surface colour with a blur (glassmorphism).
    const card = page.locator('.glass').first()
    await expect(card).toHaveCSS('backdrop-filter', /blur\(12px\)/)
  })

  test('TC_UI_005 — Inter is the UI typeface', async ({ page }) => {
    await expect(page.locator('body')).toHaveCSS('font-family', /Inter/)
  })

  test('landing page shows example questions and feature cards', async ({ page }) => {
    await expect(page.getByText('Where is the JWT generated?')).toBeVisible()
    await expect(page.getByText('Explain how the backend communicates with the frontend')).toBeVisible()

    await expect(page.getByRole('heading', { name: 'Local embeddings' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Grounded answers' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Read-only by design' })).toBeVisible()
  })

  test('backend status pill reflects health', async ({ page }) => {
    await expect(page.getByText('Backend online')).toBeVisible()
  })

  test('missing Gemini key is surfaced as a degraded pill', async ({ page }) => {
    await mockApi(page, { health: DEGRADED })
    await page.reload()
    await expect(page.getByText('Gemini key missing')).toBeVisible()
  })

  test('previously indexed repositories are offered as shortcuts', async ({ page }) => {
    await mockApi(page, {
      repositories: [
        {
          repo_id: 'pallets__flask',
          full_name: 'pallets/flask',
          html_url: 'https://github.com/pallets/flask',
          stage: 'ready',
          indexed_at: '2026-07-30T12:31:53Z',
          total_chunks: 1328,
        },
      ],
    })
    await page.reload()

    await expect(page.getByText('Already indexed on this server')).toBeVisible()
    // Named precisely: a sample-repository chip carries the same repository name.
    const shortcut = page.getByRole('button', { name: 'pallets/flask 1328 chunks' })
    await expect(shortcut).toBeVisible()

    await shortcut.click()
    await expect(page.getByRole('textbox', { name: 'Question' })).toBeVisible()
  })
})

test.describe('TC_UI_004 — Responsive layout', () => {
  const viewports = [
    { name: 'desktop', width: 1440, height: 900 },
    { name: 'laptop', width: 1280, height: 800 },
    { name: 'tablet', width: 768, height: 1024 },
    { name: 'mobile', width: 390, height: 844 },
  ]

  for (const viewport of viewports) {
    test(`no horizontal overflow at ${viewport.name} (${viewport.width}px)`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height })
      await page.goto('/')

      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      await expect(page.getByLabel('GitHub repository URL')).toBeVisible()
      await expect(page.getByRole('button', { name: /index repository/i })).toBeVisible()

      // Polled rather than sampled once: entrance animations translate elements
      // for a few frames after a resize, which can briefly widen the document.
      await expect
        .poll(
          () =>
            page.evaluate(
              () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
            ),
          { timeout: 5_000 },
        )
        .toBeLessThanOrEqual(1)
    })
  }

  test('workspace adapts: sidebar inline on desktop, drawer on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    await page.getByLabel('GitHub repository URL').fill('https://github.com/pallets/flask')
    await page.getByRole('button', { name: /index repository/i }).click()

    // Desktop: the dashboard sits beside the chat.
    await expect(page.getByRole('heading', { name: 'flask', exact: true })).toBeVisible()

    // Mobile: it collapses behind a toggle rather than squeezing the chat.
    await page.setViewportSize({ width: 390, height: 844 })
    await expect(page.getByRole('textbox', { name: 'Question' })).toBeVisible()
    // The dashboard steps aside instead of squeezing the chat.
    await expect(page.getByRole('region', { name: 'Repository details' })).toBeHidden()
    await expect
      .poll(
        () =>
          page.evaluate(
            () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
          ),
        { timeout: 5_000 },
      )
      .toBeLessThanOrEqual(1)
  })
})

test.describe('Module 2 — URL validation (client side)', () => {
  test('TC_REPO_002 — empty URL shows a validation message', async ({ page }) => {
    await page.getByRole('button', { name: /index repository/i }).click()
    await expect(page.getByText('Paste a GitHub repository URL to get started.')).toBeVisible()
    // Still on the landing page: nothing was submitted.
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  })

  const invalid = [
    { id: 'TC_REPO_003', value: 'not-a-url' },
    { id: 'TC_REPO_004', value: 'https://github.com/onlyowner' },
    { id: 'TC_REPO_006', value: 'https://gitlab.com/group/project' },
    { id: 'TC_REPO_006', value: 'https://bitbucket.org/team/repo' },
  ]

  for (const { id, value } of invalid) {
    test(`${id} — rejects ${value}`, async ({ page }) => {
      await page.getByLabel('GitHub repository URL').fill(value)
      await page.getByRole('button', { name: /index repository/i }).click()

      await expect(page.getByText('That does not look like a GitHub repository URL.')).toBeVisible()
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    })
  }

  const accepted = [
    { id: 'TC_REPO_001', value: 'https://github.com/pallets/flask' },
    { id: 'TC_REPO_007', value: 'https://github.com/pallets/flask/' },
    { id: 'TC_REPO_008', value: 'https://github.com/pallets/flask.git' },
    { id: 'deep link', value: 'https://github.com/pallets/flask/tree/main/src' },
    { id: 'no scheme', value: 'github.com/pallets/flask' },
  ]

  for (const { id, value } of accepted) {
    test(`${id} — accepts ${value}`, async ({ page }) => {
      await page.getByLabel('GitHub repository URL').fill(value)
      await page.getByRole('button', { name: /index repository/i }).click()

      await expect(page.getByRole('textbox', { name: 'Question' })).toBeVisible()
    })
  }

  test('validation message clears as soon as the user edits the field', async ({ page }) => {
    await page.getByRole('button', { name: /index repository/i }).click()
    await expect(page.getByText('Paste a GitHub repository URL to get started.')).toBeVisible()

    await page.getByLabel('GitHub repository URL').fill('h')
    await expect(page.getByText('Paste a GitHub repository URL to get started.')).toBeHidden()
  })

  test('sample repository chips populate the field', async ({ page }) => {
    await page.getByRole('button', { name: 'tiangolo/fastapi' }).click()
    await expect(page.getByLabel('GitHub repository URL')).toHaveValue(
      'https://github.com/tiangolo/fastapi',
    )
  })
})
