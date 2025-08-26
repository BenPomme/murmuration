import { test, expect } from '@playwright/test'

test.describe('Murmuration App', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('has title and heading', async ({ page }) => {
    // Expect a title "to contain" a substring.
    await expect(page).toHaveTitle(/Murmuration/)
    
    // Expect h1 to be visible
    await expect(page.locator('h1')).toHaveText('Murmuration')
    
    // Expect subtitle to be present
    await expect(page.locator('.subtitle')).toHaveText('Evolving Flock Simulation')
  })

  test('counter functionality works', async ({ page }) => {
    // Get the counter display
    const counterDisplay = page.locator('.count-value')
    
    // Should start at 0
    await expect(counterDisplay).toHaveText('0')
    
    // Click increment button
    await page.click('button[aria-label="Increase counter"]')
    await expect(counterDisplay).toHaveText('1')
    
    // Click increment again
    await page.click('button[aria-label="Increase counter"]')
    await expect(counterDisplay).toHaveText('2')
    
    // Click decrement button
    await page.click('button[aria-label="Decrease counter"]')
    await expect(counterDisplay).toHaveText('1')
  })

  test('has accessible structure', async ({ page }) => {
    // Check for main landmark
    await expect(page.locator('[role="main"]')).toBeVisible()
    
    // Check for proper headings structure
    await expect(page.locator('h1')).toBeVisible()
    await expect(page.locator('h2')).toHaveCount(2) // Counter Demo + Simulation
    
    // Check counter has proper ARIA attributes
    await expect(page.locator('[role="status"][aria-live="polite"]')).toBeVisible()
    
    // Check buttons have proper labels
    await expect(page.locator('button[aria-label="Increase counter"]')).toBeVisible()
    await expect(page.locator('button[aria-label="Decrease counter"]')).toBeVisible()
  })

  test('simulation section is present', async ({ page }) => {
    // Check simulation section exists
    await expect(page.locator('.simulation-section')).toBeVisible()
    await expect(page.locator('#sim-heading')).toHaveText('Simulation')
    
    // Check placeholder content
    await expect(page.locator('.simulation-placeholder')).toBeVisible()
    await expect(page.locator('.simulation-placeholder')).toContainText('Simulation Coming Soon')
  })

  test('footer has version information', async ({ page }) => {
    await expect(page.locator('.app-footer')).toBeVisible()
    await expect(page.locator('.app-footer')).toContainText('Murmuration v0.1.0')
    await expect(page.locator('.app-footer')).toContainText('React + TypeScript + PixiJS')
  })

  test('responsive design works', async ({ page }) => {
    // Test desktop layout
    await page.setViewportSize({ width: 1200, height: 800 })
    await expect(page.locator('.app-main')).toBeVisible()
    
    // Test mobile layout
    await page.setViewportSize({ width: 375, height: 667 })
    await expect(page.locator('.app-main')).toBeVisible()
    await expect(page.locator('.counter-section')).toBeVisible()
    await expect(page.locator('.simulation-section')).toBeVisible()
  })

  test('keyboard navigation works', async ({ page }) => {
    // Tab through interactive elements
    await page.keyboard.press('Tab') // Skip link
    await page.keyboard.press('Tab') // Decrease button
    await expect(page.locator('button[aria-label="Decrease counter"]')).toBeFocused()
    
    await page.keyboard.press('Tab') // Increase button
    await expect(page.locator('button[aria-label="Increase counter"]')).toBeFocused()
    
    // Test button activation with keyboard
    await page.keyboard.press('Enter')
    await expect(page.locator('.count-value')).toHaveText('1')
  })
})