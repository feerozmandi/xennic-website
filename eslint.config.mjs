import { defineConfig, globalIgnores } from 'eslint/config'
import nextVitals from 'eslint-config-next/core-web-vitals'
import nextTypeScript from 'eslint-config-next/typescript'

export default defineConfig([
  ...nextVitals,
  ...nextTypeScript,
  globalIgnores([
    '.next/**',
    'src/payload-types.ts',
    'src/app/(payload)/admin/importMap.js',
    // The Declare build is generated, minified output of `declarec`, committed
    // because it is what the browser downloads. Linting a compiler's output
    // says nothing about this repository's code. `declare-apps/` is the source
    // and is checked by `declare-verify`, not by ESLint.
    'public/declare-platform/**',
    'declare-apps/**',
  ]),
])
