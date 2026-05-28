/**
 * UI Screenshot Tour — captures every meaningful state of the NEOMI Pipeline Runner UI
 * Run: node screenshot_tour.js [URL]
 */

import { chromium } from 'playwright'
import { mkdir } from 'fs/promises'
import { existsSync } from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SCREENSHOTS_DIR = path.join(__dirname, 'screenshots')

const FRONTEND_URL = process.argv[2] || 'https://neomi-pipeline-ui-643234238822.europe-west1.run.app'

async function shot(page, name, description) {
  const filePath = path.join(SCREENSHOTS_DIR, `${name}.png`)
  await page.screenshot({ path: filePath, fullPage: false })
  console.log(`✓ ${name}: ${description}`)
  return filePath
}

async function run() {
  if (!existsSync(SCREENSHOTS_DIR)) {
    await mkdir(SCREENSHOTS_DIR, { recursive: true })
  }

  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  })

  const page = await browser.newPage()
  await page.setViewportSize({ width: 1440, height: 900 })

  console.log(`\nNEOMI Pipeline Runner — UI Screenshot Tour`)
  console.log(`URL: ${FRONTEND_URL}\n`)

  // ── 01: Initial page load ──────────────────────────────────────────────────
  await page.goto(FRONTEND_URL, { waitUntil: 'networkidle', timeout: 30000 })
  await shot(page, '01_initial_load', 'Oldal betöltése — üres állapot')

  // ── 02: Left panel close-up ────────────────────────────────────────────────
  await page.setViewportSize({ width: 1440, height: 900 })
  await shot(page, '02_left_panel', 'Bal panel — kísérlet választó és bemeneti form')

  // ── 03: Experiment selector interaction ────────────────────────────────────
  const expSelector = page.locator('select, [role="listbox"], [role="combobox"]').first()
  if (await expSelector.isVisible()) {
    await expSelector.click()
    await page.waitForTimeout(500)
    await shot(page, '03_experiment_dropdown', 'Kísérlet legördülő lista nyitva')
    await page.keyboard.press('Escape')
  }

  // ── 04: Fill in company name ───────────────────────────────────────────────
  const inputs = page.locator('input[type="text"], input:not([type]), textarea')
  const firstInput = inputs.first()
  await firstInput.click()
  await firstInput.fill('Acme Solutions Kft.')
  await page.waitForTimeout(300)
  await shot(page, '04_company_name_filled', 'Cégnév kitöltve — Run gomb aktív')

  // ── 05: Fill all fields ────────────────────────────────────────────────────
  const allInputs = await inputs.all()
  const fieldValues = [
    'Acme Solutions Kft.',
    'IT infrastruktúra tanácsadás',
    'Felsővezetők (C-szint)',
    'AI stratégiai készségek fejlesztése',
    'A cég 50 főt foglalkoztat, főként technológiai szektorban működik.',
  ]
  for (let i = 0; i < Math.min(allInputs.length, fieldValues.length); i++) {
    await allInputs[i].fill(fieldValues[i])
  }
  await page.waitForTimeout(300)
  await shot(page, '05_all_fields_filled', 'Összes mező kitöltve')

  // ── 06: Run button state ───────────────────────────────────────────────────
  const runBtn = page.locator('button').filter({ hasText: /pipeline/i }).first()
  if (await runBtn.isVisible()) {
    await shot(page, '06_run_button_active', 'Pipeline futtatása gomb aktív állapotban')
  }

  // ── 07: Click Run and capture loading state ────────────────────────────────
  if (await runBtn.isVisible() && await runBtn.isEnabled()) {
    await runBtn.click()
    await page.waitForTimeout(1500)
    await shot(page, '07_pipeline_loading', 'Pipeline fut — betöltési állapot')

    // Wait for result (up to 90 seconds)
    console.log('  Várakozás a pipeline eredményre (max 90s)...')
    try {
      await page.waitForFunction(
        () => {
          const dots = document.querySelector('[style*="loadingDots"], [style*="loading"]')
          const result = document.querySelectorAll('[style*="nodeCard"], [style*="card"]')
          return !dots && result.length > 0
        },
        { timeout: 90000 }
      )
    } catch {
      // timeout — take screenshot of whatever state we're in
    }
    await page.waitForTimeout(1000)
    await shot(page, '08_pipeline_result', 'Pipeline eredmény — node trace-ek és kritika')

    // ── 09: Expand first node card ─────────────────────────────────────────
    const nodeCards = page.locator('[role="button"]')
    if (await nodeCards.count() > 0) {
      await nodeCards.first().click()
      await page.waitForTimeout(400)
      await shot(page, '09_node_expanded', 'Node kártya kinyitva — tartalom látható')
    }

    // ── 10: Full page scroll-down ──────────────────────────────────────────
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    await page.waitForTimeout(300)
    await shot(page, '10_result_bottom', 'Eredmény panel alja — kritikai összefoglaló')

    // ── 11: SRS badge hover ────────────────────────────────────────────────
    const srsBadge = page.locator('div').filter({ hasText: /^SRS/ }).first()
    if (await srsBadge.count() > 0) {
      await srsBadge.hover()
      await page.waitForTimeout(400)
      await shot(page, '11_srs_tooltip', 'SRS badge tooltip — részletes pontszámok')
    }
  }

  // ── 12: Empty required field validation ───────────────────────────────────
  await page.goto(FRONTEND_URL, { waitUntil: 'networkidle', timeout: 15000 })
  const runBtnFresh = page.locator('button').filter({ hasText: /pipeline/i }).first()
  if (await runBtnFresh.isVisible()) {
    await shot(page, '12_validation_empty', 'Üres cégnév — gomb letiltva, figyelmeztető szöveg')
  }

  await browser.close()
  console.log('\nScreenshotok elmentve:', SCREENSHOTS_DIR)
}

run().catch(err => {
  console.error('Hiba:', err.message)
  process.exit(1)
})
