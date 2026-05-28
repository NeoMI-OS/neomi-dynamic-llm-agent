/**
 * NEOMI Pipeline Runner — UI Screenshot Tour
 * Captures every meaningful state of the frontend
 * Run: node screenshot_tour.mjs [URL]
 */

import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs'
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
  console.log(`  ✓ ${name} — ${description}`)
  return filePath
}

async function run() {
  await mkdir(SCREENSHOTS_DIR, { recursive: true })

  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  })

  const page = await browser.newPage()
  await page.setViewportSize({ width: 1440, height: 900 })

  console.log(`\nNEOMI Pipeline Runner — UI Screenshot Tour`)
  console.log(`URL: ${FRONTEND_URL}\n`)

  // ── 01: Initial page load ─────────────────────────────────────────────────
  console.log('[1/7] Oldal betöltése...')
  await page.goto(FRONTEND_URL, { waitUntil: 'networkidle', timeout: 30000 })
  await page.waitForTimeout(1000)
  await shot(page, '01_initial_load', 'Kezdőképernyő — üres állapot')

  // ── 02: Experiment selector ───────────────────────────────────────────────
  console.log('[2/7] Kísérlet választó...')
  // Look for any dropdown/select element
  const selectEl = page.locator('select').first()
  if (await selectEl.count() > 0) {
    await selectEl.click()
    await page.waitForTimeout(500)
    await shot(page, '02_experiment_selector', 'Kísérlet kiválasztó — legördülő lista')
    await page.keyboard.press('Escape')
  } else {
    await shot(page, '02_experiment_selector', 'Bal panel — kísérlet és bemeneti mezők')
  }

  // ── 03: Fill company name only ────────────────────────────────────────────
  console.log('[3/7] Bemeneti mezők kitöltése...')
  const firstInput = page.locator('input').first()
  await firstInput.fill('Acme Solutions Kft.')
  await page.waitForTimeout(400)
  await shot(page, '03_company_name_filled', 'Cégnév kitöltve — Run gomb aktívvá válik')

  // ── 04: All fields filled ─────────────────────────────────────────────────
  const allInputs = page.locator('input, textarea')
  const count = await allInputs.count()
  const testValues = [
    'Acme Solutions Kft.',
    'IT infrastruktúra tanácsadás',
    'Felsővezetők (C-szint)',
    'AI stratégiai készségek fejlesztése',
    'A cég 50 főt foglalkoztat, főként technológiai szektorban működik.',
  ]
  for (let i = 0; i < Math.min(count, testValues.length); i++) {
    const inp = allInputs.nth(i)
    const val = await inp.inputValue()
    if (!val) await inp.fill(testValues[i])
  }
  await page.waitForTimeout(400)
  await shot(page, '04_all_fields_filled', 'Összes bemeneti mező kitöltve')

  // ── 05: Run pipeline ──────────────────────────────────────────────────────
  console.log('[4/7] Pipeline indítása...')
  const runBtn = page.locator('button').filter({ hasText: /pipeline|futtat/i }).first()
  if (await runBtn.isEnabled()) {
    await runBtn.click()
    await page.waitForTimeout(2000)
    await shot(page, '05_pipeline_loading', 'Pipeline fut — betöltési animáció')

    // ── 06: Wait for result ───────────────────────────────────────────────
    console.log('[5/7] Várakozás az eredményre (max 90s)...')
    try {
      await page.waitForFunction(
        () => {
          // Check if loading indicator is gone and some result content appeared
          const body = document.body.innerText
          return body.includes('csomópont') || body.includes('Kritikai') || body.includes('node') || body.includes('Visszajelzés')
        },
        { timeout: 90000 }
      )
      await page.waitForTimeout(1500)
      await shot(page, '06_pipeline_result_full', 'Pipeline eredmény — teljes nézet')

      // ── 07: Expand a node card ──────────────────────────────────────────
      console.log('[6/7] Node kártya kinyitása...')
      // Try clicking on any clickable card header
      const clickableCards = page.locator('[role="button"], div[style*="cursor: pointer"]')
      const cardCount = await clickableCards.count()
      if (cardCount > 0) {
        await clickableCards.first().click()
        await page.waitForTimeout(600)
        await shot(page, '07_node_card_expanded', 'Node kártya kinyitva — LLM kimenet látható')
      }

      // ── 08: SRS badge hover ─────────────────────────────────────────────
      console.log('[7/7] SRS badge tooltip...')
      const srsBadge = page.locator('div').filter({ hasText: /^SRS\s*[\d.]/ }).first()
      if (await srsBadge.count() > 0) {
        await srsBadge.hover()
        await page.waitForTimeout(500)
        await shot(page, '08_srs_badge_tooltip', 'SRS badge tooltip — tudás/érvelés/használhatóság bontás')
      }

      // ── 09: Full page with critic summary ──────────────────────────────
      await page.evaluate(() => {
        const panels = document.querySelectorAll('[style*="overflowY"]')
        panels.forEach(p => p.scrollTop = 99999)
      })
      await page.waitForTimeout(400)
      await shot(page, '09_critic_summary', 'Kritikai összefoglaló — érettségi pontszám és visszajelzés')

    } catch (e) {
      console.log('  Timeout vagy hiba a pipeline futtatásakor:', e.message)
      await shot(page, '06_timeout_state', 'Timeout állapot')
    }
  } else {
    console.log('  Run gomb nem elérhető.')
  }

  // ── 10: Disabled state (no company name) ──────────────────────────────────
  await page.goto(FRONTEND_URL, { waitUntil: 'networkidle', timeout: 15000 })
  await page.waitForTimeout(800)
  await shot(page, '10_validation_empty', 'Üres állapot — kötelező mező figyelmeztetés, Run gomb inaktív')

  await browser.close()

  console.log(`\n✅ Screenshotok elmentve: ${SCREENSHOTS_DIR}`)
  console.log('Fájlok:')
  const { readdirSync } = await import('fs')
  readdirSync(SCREENSHOTS_DIR).forEach(f => console.log(`  - ${f}`))
}

run().catch(err => {
  console.error('\n❌ Hiba:', err.message)
  process.exit(1)
})
