module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    '@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', '.eslintrc.cjs', 'vite.config.ts', 'playwright.config.ts'],
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  plugins: ['react-refresh'],
  rules: {
    // React specific rules
    'react-refresh/only-export-components': [
      'warn',
      { allowConstantExport: true },
    ],

    // TypeScript specific rules for strict mode compliance as per CLAUDE.md
    '@typescript-eslint/no-unused-vars': 'error',
    '@typescript-eslint/no-explicit-any': 'error',
    '@typescript-eslint/no-non-null-assertion': 'warn',
    '@typescript-eslint/prefer-nullish-coalescing': 'error',
    '@typescript-eslint/prefer-optional-chain': 'error',

    // General code quality rules
    'no-console': 'warn',
    'prefer-const': 'error',
    'no-var': 'error',
    
    // Ensure accessibility considerations
    'no-restricted-syntax': [
      'error',
      {
        'selector': 'JSXElement[openingElement.name.name="img"]:not([openingElement.attributes.*.name.name="alt"])',
        'message': 'Images must have alt attributes for accessibility'
      }
    ]
  },
  settings: {
    react: {
      version: 'detect',
    },
  },
}