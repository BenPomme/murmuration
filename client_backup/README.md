# Murmuration Client

React + TypeScript + PixiJS frontend for the Murmuration flock simulation game.

## Tech Stack

- **React 18** - UI library with Function Components only
- **TypeScript** - Strict mode enabled, no `any` types
- **Vite** - Build tool and dev server
- **PixiJS** - WebGL rendering for simulation
- **Vitest** - Unit testing framework
- **Playwright** - E2E testing framework
- **ESLint** - Code linting with TypeScript rules

## Development

### Prerequisites

- Node.js 18+ 
- npm 9+

### Getting Started

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run unit tests
npm test

# Run E2E tests
npm run e2e

# Lint code
npm run lint
```

### Scripts

- `npm run dev` - Start Vite dev server on port 3000
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm test` - Run Vitest unit tests
- `npm run test:coverage` - Run tests with coverage
- `npm run e2e` - Run Playwright E2E tests
- `npm run lint` - Run ESLint

## Architecture

### Directory Structure

```
src/
├── components/          # Reusable React components
├── hooks/              # Custom React hooks
├── services/           # API and external service logic
├── simulation/         # PixiJS simulation components
├── stores/             # State management
├── types/              # TypeScript type definitions
├── utils/              # Utility functions
├── __tests__/          # Unit tests
├── App.tsx             # Main App component
├── main.tsx            # React entry point
├── index.css           # Global styles
└── setupTests.ts       # Test configuration
```

### Key Features

- **Accessibility First**: WCAG 2.1 AA compliant, keyboard navigation, screen reader support
- **Type Safety**: Strict TypeScript configuration with no `any` types
- **Performance**: Code splitting, lazy loading, optimized bundles
- **Testing**: Comprehensive unit and E2E test coverage (>80% target)
- **Responsive**: Mobile-first design, supports all screen sizes

## Code Standards

### TypeScript

- Strict mode enabled in `tsconfig.json`
- No `any` or implicit `any` types allowed
- Prefer explicit return types for functions
- Use proper error handling with typed errors

### React

- Function components only (no class components)
- Use hooks for state management
- Proper prop typing with interfaces
- Accessibility attributes on all interactive elements

### Testing

- Unit tests for all components and utilities
- E2E tests for critical user flows
- Accessibility testing included in E2E suite
- Minimum 80% code coverage

### Accessibility

- Semantic HTML elements
- ARIA attributes where needed
- Keyboard navigation support
- Colorblind-safe color palette
- Reduced motion support
- Screen reader compatibility

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

## Performance Requirements

As per CLAUDE.md specifications:

- **Target**: ≥300 agents @ 60Hz on dev laptop
- **CI Minimum**: ≥150 agents @ 60Hz headless
- **UI Responsiveness**: No hitch >16ms during simulation

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Contributing

1. Follow the TypeScript strict mode requirements
2. Write tests for new components/features
3. Run linting and type checking before commits
4. Ensure accessibility standards are met
5. Keep bundle size optimized

## Deployment

The client builds to static files in the `dist/` directory and can be served by any static file server or CDN.