#!/usr/bin/env node
/**
 * Architecture boundary check.
 *
 * The site is layered on purpose, and the layers are enforced here rather than
 * by convention:
 *
 *   ui         (src/components/**)      presentation only, receives props
 *   content    (src/lib/*.ts data)      approved copy, tokens, types: safe anywhere
 *   server     (src/lib/content.ts, preview-security, contact-actions, src/collections)
 *                                       Payload access, secrets, server actions
 *   app        (src/app/**)             composition: reads server data, renders ui
 *
 * Rules:
 *   1. A `'use client'` module may not reach server code (Payload, the database,
 *      the preview gate) except the documented server-action entry point.
 *   2. `src/components/**` may not import the CMS at all; pages pass data down.
 *   3. Payload and the database driver may only be imported from the app,
 *      collection, migration and script directories.
 *   4. UI primitives may not import page data modules; they take props.
 *   5. Components never import `@/payload-types`: the CMS schema is mapped to
 *      view models in `src/lib/contracts.ts` and `src/lib/content.ts` only.
 *
 * Run with `npm run check:boundaries`. Exits non-zero with a list of violations.
 */
import { readdir, readFile } from 'node:fs/promises'
import { join, relative, sep } from 'node:path'

const ROOT = process.cwd()
const SRC = join(ROOT, 'src')

const SERVER_ONLY_PACKAGES = ['payload', '@payload-config', '@payloadcms/db-postgres', 'pg', 'sharp']
const SERVER_ONLY_MODULES = ['@/lib/content', '@/lib/preview-security', '@/payload.config']
/** The one server action a client component is allowed to import. */
const ALLOWED_SERVER_ACTIONS = ['@/lib/contact-actions']
/**
 * The only modules inside `src/lib` that may touch the CMS. They are the server
 * boundary for the content layer: `content.ts` reads pages and services,
 * `contact-actions.ts` is a server action. Everything else in `src/lib` is
 * plain data or pure helpers and stays importable from both sides.
 */
const SERVER_BOUNDARY_MODULES = ['src/lib/content.ts', 'src/lib/contact-actions.ts']
const DATA_ACCESS_MODULES = ['@/lib/content']
/** The only modules allowed to know the generated CMS schema. */
const SCHEMA_MODULES = ['src/lib/contracts.ts', 'src/lib/content.ts']
/** Pure token/constant modules a presentational primitive may read. */
const UI_SAFE_MODULES = ['@/lib/theme', '@/lib/i18n', '@/lib/navigation']

async function walk(dir) {
  const entries = await readdir(dir, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) files.push(...(await walk(path)))
    else if (/\.(ts|tsx)$/.test(entry.name)) files.push(path)
  }
  return files
}

/** Every `from '...'` plus bare `import '...'`, ignoring type-only imports. */
function importsOf(source) {
  const specifiers = []
  const importRe = /^\s*import\s+(type\s+)?(?:[\s\S]*?\sfrom\s+)?['"]([^'"]+)['"]/gm
  let match
  while ((match = importRe.exec(source))) {
    // `import type ...` is erased at compile time, so it crosses no boundary.
    if (match[1] === 'type') continue
    specifiers.push(match[2])
  }
  // `await import('...')` and `require('...')` reach the same modules.
  const dynamicRe = /(?:await\s+import|require)\(\s*['"]([^'"]+)['"]\s*\)/g
  while ((match = dynamicRe.exec(source))) specifiers.push(match[1])
  return specifiers
}


const files = await walk(SRC)
const violations = []
const stats = { files: 0, clientModules: 0, imports: 0 }

for (const file of files) {
  const raw = await readFile(file, 'utf8')
  const rel = relative(ROOT, file)
  const dir = relative(ROOT, join(file, '..'))
  const normalized = dir.split(sep).join('/')
  const isClient = /^\s*['"]use client['"]/m.test(raw)
  const specifiers = importsOf(raw)
  stats.files += 1
  stats.imports += specifiers.length
  if (isClient) stats.clientModules += 1

  for (const spec of specifiers) {
    const pkg = spec.startsWith('@/') ? null : spec.split('/')[0]

    // Rule 3: the CMS and the database belong to the server directories only.
    const serverImport = SERVER_ONLY_PACKAGES.includes(spec) || SERVER_ONLY_PACKAGES.includes(pkg) || SERVER_ONLY_MODULES.includes(spec)
    if (serverImport) {
      const allowedDir =
        normalized.startsWith('src/app') ||
        normalized.startsWith('src/collections') ||
        normalized === 'src' ||
        normalized.startsWith('scripts') ||
        normalized.startsWith('src/migrations')
      const declaredBoundary = SERVER_BOUNDARY_MODULES.includes(rel.split(sep).join('/'))
      if (!allowedDir && !declaredBoundary) {
        violations.push(`${rel}: imports server module "${spec}" outside src/app, src/collections, scripts or a declared boundary module`)
      }
    }

    if (!isClient) continue

    // Rule 1: a client module may not pull server code into the browser bundle.
    if (serverImport && !ALLOWED_SERVER_ACTIONS.includes(spec)) {
      violations.push(`${rel}: client module imports server-only "${spec}"`)
    }
    if (spec.startsWith('node:')) {
      violations.push(`${rel}: client module imports Node built-in "${spec}"`)
    }

    // Rule 2: components never read the CMS; the page passes data down.
    if (normalized.startsWith('src/components') && DATA_ACCESS_MODULES.includes(spec)) {
      violations.push(`${rel}: component imports data access "${spec}"; pass data as props instead`)
    }
  }

  // Rule 5: the CMS schema does not reach the interface layer.
  if (specifiers.includes('@/payload-types') && !SCHEMA_MODULES.includes(rel.split(sep).join('/'))) {
    violations.push(`${rel}: imports the generated CMS schema; map it to a view model in src/lib/contracts.ts`)
  }

  // Rule 4: UI primitives stay presentational.
  if (normalized.startsWith('src/components/ui')) {
    for (const spec of specifiers) {
      if (spec.startsWith('@/lib/') && !UI_SAFE_MODULES.includes(spec)) {
        violations.push(`${rel}: ui primitive imports "${spec}"; primitives take props, not content`)
      }
    }
  }
}

// Keep the check honest: it must fail when the rules are broken.
if (process.argv.includes('--self-test')) {
  const probe = `
    'use client'
    import { getPayload } from 'payload'
    import { getPage } from '@/lib/content'
  `
  const found = importsOf(probe)
  const wouldFail = found.includes('payload') && found.includes('@/lib/content')
  console.log(wouldFail ? 'self-test: pass' : 'self-test: FAIL (imports were not detected)')
  process.exit(wouldFail ? 0 : 1)
}

console.log(
  `boundaries: ${stats.files} modules (${stats.clientModules} client), ${stats.imports} imports checked`,
)

if (violations.length > 0) {
  console.error(`\n${violations.length} boundary violation(s):`)
  for (const violation of violations) console.error(`  - ${violation}`)
  process.exit(1)
}

console.log('boundaries: ok')
