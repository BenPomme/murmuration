import { FullConfig } from '@playwright/test'

/**
 * Global setup for Playwright E2E tests
 * Sets up accessibility testing configuration as per CLAUDE.md requirements
 */
async function globalSetup(config: FullConfig): Promise<void> {
  // Set environment variables for consistent testing
  process.env.NODE_ENV = 'test'
  process.env.VITE_APP_ENV = 'test'
  
  // Ensure deterministic behavior for testing
  process.env.TZ = 'UTC'
  
  console.log('🧪 Global E2E setup completed')
  console.log(`Running on ${config.projects.length} browser configurations`)
}

export default globalSetup