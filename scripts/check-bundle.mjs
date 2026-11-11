#!/usr/bin/env node
/**
 * Client-bundle secret check.
 *
 * Everything under `.next/static` is downloaded by the browser. This script
 * fails the build if a secret-shaped string or a configured environment value
 * ended up there, which is the only reliable proof that server configuration
 * did not leak into the public bundle.
 *
 * Run after `npm run build`:  npm run check:bundle
 */
import { readdir, readFile, stat } from 'node:fs/promises'
import { join, relative } from 'node:path'

const ROOT = process.cwd()
const STATIC = join(ROOT, '.next', 'static')

/** Strings that must never appear in a browser bundle. */
const FORBIDDEN = [
  'DATABASE_URL',
  'PAYLOAD_SECRET',
  'PREVIEW_ORIGIN',
  'AGE_RECIPIENT',
  'backup-identity',
  'preview-deploy',
  'postgres://',
  'postgresql://',
  '@payloadcms/db-postgres',
]

/** Environment values that would be a leak if they were inlined. */
const SECRET_ENV = ['DATABASE_URL', 'PAYLOAD_SECRET', 'PREVIEW_DATABASE_URL', 'PREVIEW_PAYLOAD_SECRET']

async function walk(dir) {
  const out = []
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) out.push(...(await walk(path)))
    else if (/\.(js|mjs|css|map)$/.test(entry.name)) out.push(path)
  }
  return out
}

try {
  await stat(STATIC)
} catch {
  console.error('check:bundle needs a build first (.next/static is missing). Run `npm run build`.')
  process.exit(1)
}

const files = await walk(STATIC)
const needles = [...FORBIDDEN]
for (const name of SECRET_ENV) {
  const value = process.env[name]
  if (value && value.length >= 8) needles.push(value)
}

const hits = []
let bytes = 0
for (const file of files) {
  const content = await readFile(file, 'utf8')
  bytes += content.length
  for (const needle of needles) {
    if (content.includes(needle)) hits.push(`${relative(ROOT, file)} contains "${needle.slice(0, 24)}"`)
  }
}

console.log(
  `client bundle: ${files.length} files, ${(bytes / 1024).toFixed(0)} KiB scanned, ${needles.length} markers`,
)

if (hits.length > 0) {
  console.error(`\n${hits.length} possible leak(s) in the browser bundle:`)
  for (const hit of hits.slice(0, 20)) console.error(`  - ${hit}`)
  process.exit(1)
}

console.log('client bundle: no server configuration found')
