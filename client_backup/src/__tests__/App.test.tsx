import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import App from '../App'

describe('App Component', () => {
  it('renders main heading', () => {
    render(<App />)
    const heading = screen.getByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent('Murmuration')
  })

  it('renders subtitle', () => {
    render(<App />)
    const subtitle = screen.getByText('Evolving Flock Simulation')
    expect(subtitle).toBeInTheDocument()
  })

  it('initializes counter at 0', () => {
    render(<App />)
    const counterValue = screen.getByRole('status')
    expect(counterValue).toHaveTextContent('0')
  })

  it('increments counter when + button is clicked', () => {
    render(<App />)
    const incrementButton = screen.getByLabelText('Increase counter')
    const counterValue = screen.getByRole('status')

    fireEvent.click(incrementButton)
    expect(counterValue).toHaveTextContent('1')

    fireEvent.click(incrementButton)
    expect(counterValue).toHaveTextContent('2')
  })

  it('decrements counter when - button is clicked', () => {
    render(<App />)
    const incrementButton = screen.getByLabelText('Increase counter')
    const decrementButton = screen.getByLabelText('Decrease counter')
    const counterValue = screen.getByRole('status')

    // First increment to 1
    fireEvent.click(incrementButton)
    expect(counterValue).toHaveTextContent('1')

    // Then decrement back to 0
    fireEvent.click(decrementButton)
    expect(counterValue).toHaveTextContent('0')

    // Can go negative
    fireEvent.click(decrementButton)
    expect(counterValue).toHaveTextContent('-1')
  })

  it('has proper accessibility attributes', () => {
    render(<App />)
    
    // Check for main landmark
    const main = screen.getByRole('main')
    expect(main).toBeInTheDocument()
    
    // Check counter status has live region
    const counterStatus = screen.getByRole('status')
    expect(counterStatus).toHaveAttribute('aria-live', 'polite')
    
    // Check buttons have proper labels
    const incrementButton = screen.getByLabelText('Increase counter')
    const decrementButton = screen.getByLabelText('Decrease counter')
    expect(incrementButton).toBeInTheDocument()
    expect(decrementButton).toBeInTheDocument()
  })

  it('renders simulation section', () => {
    render(<App />)
    
    const simHeading = screen.getByRole('heading', { name: /simulation/i })
    expect(simHeading).toBeInTheDocument()
    
    const simPlaceholder = screen.getByText(/simulation coming soon/i)
    expect(simPlaceholder).toBeInTheDocument()
  })

  it('renders footer with version info', () => {
    render(<App />)
    
    const footer = screen.getByText(/murmuration v0\.1\.0/i)
    expect(footer).toBeInTheDocument()
    
    const techStack = screen.getByText(/react \+ typescript \+ pixijs/i)
    expect(techStack).toBeInTheDocument()
  })
})