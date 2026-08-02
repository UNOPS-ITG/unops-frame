import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'vendor', 'coverage', 'playwright-report'] },

  {
    extends: [js.configs.recommended, ...tseslint.configs.recommendedTypeChecked],
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
      parserOptions: {
        project: ['./tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],

      /* --- Frame invariants, enforced rather than documented ---------------
         PM-4 says permission evaluation has exactly one implementation and it
         is not in the client. These identifiers are how a second one arrives:
         someone adds a helper "just for the UI" and it drifts from the server.
         The client renders what the trimmed row page tells it and decides
         nothing. See tools/fitness for the structural half of this. */
      'no-restricted-syntax': [
        'error',
        {
          selector:
            "Identifier[name=/^(canRead|canWrite|canEdit|canDelete|isAllowed|hasPermission|checkPermission|validateField|evaluateRule)$/]",
          message:
            'Permission and validation logic lives on the server only (PM-4, BP-4). The client consumes the trimmed row page and its rendering hints. If you need a new hint, add it to the wire contract.',
        },
      ],
    },
  },

  // Build config and the fitness suite: Node, TypeScript, but untyped linting —
  // they are tooling, not shipped code, and do not need the type-aware pass.
  {
    files: ['*.config.ts', 'tools/**/*.ts'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: { globals: globals.node },
    rules: {
      '@typescript-eslint/no-non-null-assertion': 'off',
    },
  },

  // Inherited dev scripts, carried over from the sibling repo. Several are
  // slated for rewrite or deletion, so their existing debt is surfaced as
  // warnings rather than blocking every commit until that triage happens.
  // validate-palette.mjs runs in both Node and a browser, hence both globals.
  {
    files: ['scripts/**/*.mjs'],
    extends: [js.configs.recommended],
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
    rules: {
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    },
  },
)
