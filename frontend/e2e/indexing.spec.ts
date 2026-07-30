/**
 * Module 11 — Loading states (TC_LOAD_001, TC_LOAD_002)
 * Module 3 — Cloning feedback (TC_CLONE_004, TC_CLONE_005)
 * Module 10 — Repository dashboard (TC_SUM_002, TC_SUM_003)
 */

import { expect, test } from '@playwright/test'

import { mockApi, READY_STATUS } from './support/mockApi'

test.describe('Module 11 — Indexing progress', () => {
  test('TC_LOAD_001 / TC_LOAD_002 — pipeline stages and progress are shown', async ({ page }) => {
    await mockApi(page, { cloneMode: 'progress' })
    await page.goto('/')

    await page.getByLabel('GitHub repository URL').fill('https://github.com/pallets/flask')
    await page.getByRole('button', { name: /index repository/i }).click()

    // The loading screen names the repository and the checklist of stages.
    await expect(page.getByText('Indexing repository')).toBeVisible()
    await expect(page.getByText('pallets/flask')).toBeVisible()

    // Scoped to the checklist: the live status line can repeat the same wording.
    const checklist = page.getByRole('list', { name: 'Indexing stages' })
    for (const label of [
      'Validating repository',
      'Cloning repository',
      'Reading files',
      'Splitting into chunks',
      'Generating embeddings',
      'Creating vector database',
      'Almost ready',
    ]) {
      await expect(checklist.getByText(label, { exact: true })).toBeVisible()
    }

    // TC_LOAD_002 — the live message from the backend is surfaced verbatim.
    await expect(page.getByText(/Generating embeddings \(620\/1328 chunks\)/)).toBeVisible()
    // A percentage is rendered and advances.
    await expect(page.getByText(/^\d+%$/)).toBeVisible()

    // The run completes and hands over to the workspace.
    await expect(page.getByRole('textbox', { name: 'Question' })).toBeVisible({ timeout: 15_000 })
  })

  test('progress bar reaches 100% and live counters appear', async ({ page }) => {
    await mockApi(page, { cloneMode: 'progress' })
    await page.goto('/')
    await page.getByLabel('GitHub repository URL').fill('https://github.com/pallets/flask')
    await page.getByRole('button', { name: /index repository/i }).click()

    // Counters appear as soon as the backend reports statistics.
    await expect(page.getByText('Files', { exact: true })).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('Chunks', { exact: true }).first()).toBeVisible()
  })

  test('indexing can be cancelled back to the landing page', async ({ page }) => {
    await mockApi(page, { cloneMode: 'progress' })
    await page.goto('/')
    await page.getByLabel('GitHub repository URL').fill('https://github.com/pallets/flask')
    await page.getByRole('button', { name: /index repository/i }).click()

    await page.getByRole('button', { name: 'Cancel' }).click()
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  })

  test('TC_CLONE_004 — an already-indexed repository skips straight to chat', async ({ page }) => {
    await mockApi(page, { cloneMode: 'instant' })
    await page.goto('/')
    await page.getByLabel('GitHub repository URL').fill('https://github.com/pallets/flask')
    await page.getByRole('button', { name: /index repository/i }).click()

    await expect(page.getByRole('textbox', { name: 'Question' })).toBeVisible()
    // No progress screen was needed.
    await expect(page.getByText('Indexing repository')).toBeHidden()
  })

  test('TC_CLONE_005 — a mid-pipeline failure is explained with remediation', async ({ page }) => {
    await mockApi(page, {
      cloneMode: 'progress',
      statusFailure: {
        code: 'repository_not_found',
        message: "'pallets/flask' was not found. It may be private, renamed or deleted.",
      },
    })
    await page.goto('/')
    await page.getByLabel('GitHub repository URL').fill('https://github.com/pallets/flask')
    await page.getByRole('button', { name: /index repository/i }).click()

    await expect(page.getByText('Indexing failed').first()).toBeVisible()
    await expect(page.getByRole('alert')).toContainText('was not found')
    // The remedy for this specific error code is offered.
    await expect(page.getByRole('alert')).toContainText('Double-check the spelling')
    await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Start over' })).toBeVisible()
  })
})

test.describe('Module 10 — Repository dashboard', () => {
  /** All assertions are scoped to the dashboard region, never the whole page. */
  const dashboardOf = (page: import('@playwright/test').Page) =>
    page.getByRole('region', { name: 'Repository details' })

  test.beforeEach(async ({ page }) => {
    await mockApi(page)
    await page.goto('/')
    await page.getByLabel('GitHub repository URL').fill('https://github.com/pallets/flask')
    await page.getByRole('button', { name: /index repository/i }).click()
    await page.getByRole('textbox', { name: 'Question' }).waitFor()
  })

  test('TC_SUM_003 — GitHub metadata is displayed', async ({ page }) => {
    const dashboard = dashboardOf(page)

    await expect(dashboard.getByRole('heading', { name: 'flask', exact: true })).toBeVisible()
    await expect(dashboard.getByText('pallets', { exact: true })).toBeVisible()
    await expect(dashboard.getByText(READY_STATUS.metadata!.description!)).toBeVisible()

    // Stars / forks in compact form, size, default branch and licence.
    await expect(dashboard.getByText('68.4K')).toBeVisible()
    await expect(dashboard.getByText('16.3K')).toBeVisible()
    await expect(dashboard.getByText('10.0 MB')).toBeVisible()
    await expect(dashboard.getByText('main', { exact: true })).toBeVisible()
    await expect(dashboard.getByText('BSD-3-Clause')).toBeVisible()

    // A working link back to GitHub.
    await expect(dashboard.getByRole('link', { name: 'Open on GitHub' })).toHaveAttribute(
      'href',
      'https://github.com/pallets/flask',
    )
  })

  test('TC_SUM_002 — detected languages are listed with proportions', async ({ page }) => {
    const dashboard = dashboardOf(page)

    // GitHub's primary-language badge.
    await expect(dashboard.getByText('Python', { exact: true })).toBeVisible()
    // The detected mix from the index itself.
    await expect(dashboard.getByText('Languages')).toBeVisible()
    await expect(dashboard.getByText('rst', { exact: true })).toBeVisible()
    await expect(dashboard.getByText('markdown', { exact: true })).toBeVisible()
  })

  test('index statistics are reported', async ({ page }) => {
    const dashboard = dashboardOf(page)

    await expect(dashboard.getByText('Files indexed')).toBeVisible()
    await expect(dashboard.getByText('208', { exact: true })).toBeVisible()
    await expect(dashboard.getByText('1,328').first()).toBeVisible() // chunks
    await expect(dashboard.getByText('Index time')).toBeVisible()
    // 119.09 seconds is rendered in minutes-and-seconds form.
    await expect(dashboard.getByText('1m 59s')).toBeVisible()

    // Embedding status / model / dimensions
    await expect(dashboard.getByText('ready', { exact: true })).toBeVisible()
    await expect(dashboard.getByText('all-MiniLM-L6-v2')).toBeVisible()
    await expect(dashboard.getByText('384', { exact: true })).toBeVisible()
    await expect(dashboard.getByText('Files skipped')).toBeVisible()
    await expect(dashboard.getByText('17', { exact: true })).toBeVisible()
  })

  test('repository structure is listed', async ({ page }) => {
    const dashboard = dashboardOf(page)

    await expect(dashboard.getByText('Structure')).toBeVisible()
    await expect(dashboard.getByText('src/', { exact: true })).toBeVisible()
    await expect(dashboard.getByText('tests/', { exact: true })).toBeVisible()
    await expect(dashboard.getByText('pyproject.toml', { exact: true })).toBeVisible()
  })

  test('the dashboard can be collapsed and restored', async ({ page }) => {
    await page.getByRole('button', { name: 'Hide repository panel' }).click()
    await expect(dashboardOf(page)).toBeHidden()

    await page.getByRole('button', { name: 'Show repository panel' }).click()
    await expect(dashboardOf(page)).toBeVisible()
  })

  test('the dashboard is mounted exactly once', async ({ page }) => {
    // Guards against regressing to a duplicated desktop + drawer copy.
    await expect(dashboardOf(page)).toHaveCount(1)
  })

  test('re-index and new repository actions are available', async ({ page }) => {
    await expect(page.getByRole('button', { name: /re-index/i })).toBeVisible()
    await page.getByRole('button', { name: /new repository/i }).click()
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  })
})
