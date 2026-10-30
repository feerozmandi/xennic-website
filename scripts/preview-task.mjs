// Explicit one-shot production operations. Never run on application startup.
import { spawn } from 'node:child_process'
import pg from 'pg'

const task = process.argv[2]
if (!['migrate', 'seed'].includes(task) || process.env.NODE_ENV !== 'production' || process.env.XENNIC_PREVIEW !== '1' || !process.env.DATABASE_URL || !process.env.PAYLOAD_SECRET) {
  console.error('Requires preview production environment and task migrate or seed.')
  process.exit(1)
}
const client = new pg.Client({ connectionString: process.env.DATABASE_URL })
try {
  await client.connect()
  const lock = await client.query('SELECT pg_try_advisory_lock(178282411, 1) AS acquired')
  if (!lock.rows[0].acquired) throw new Error('Another preview migration or seed is running.')
  const check = await client.query(`SELECT to_regclass('website.payload_migrations') IS NOT NULL AS ledger,
    to_regclass('shared.customers') IS NOT NULL AS customers,
    EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='website' AND c.relkind IN ('r','p')) AS website_tables`)
  if (!check.rows[0].ledger && (check.rows[0].customers || check.rows[0].website_tables)) throw new Error('Existing untracked tables: manual review required, refusing to migrate or seed.')
  if (check.rows[0].ledger) {
    const rows = await client.query('SELECT name, batch FROM website.payload_migrations')
    if (rows.rows.some(row => Number(row.batch) === -1)) throw new Error('Development schema push detected; manual review required.')
    if (rows.rows.some(row => row.name === '20261030_163225_baseline') && !check.rows[0].customers) throw new Error('Baseline is recorded but the shared customer table is missing.')
    if (task === 'seed' && !rows.rows.some(row => row.name === '20261030_163225_baseline')) throw new Error('Baseline migration is required before seed.')
  } else if (task === 'seed') throw new Error('Run migration before seed.')
  const args = task === 'migrate' ? ['node_modules/payload/bin.js', 'migrate'] : ['--import=tsx', 'scripts/seed.ts']
  const child = spawn(process.execPath, args, { env: process.env, stdio: 'ignore' })
  const code = await new Promise((resolve, reject) => { child.once('error', reject); child.once('exit', (exitCode, signal) => resolve(signal ? 1 : exitCode ?? 1)) })
  if (code !== 0) throw new Error(`${task} failed.`)
  if (task === 'migrate') {
    const table = await client.query(`SELECT to_regclass('website.payload_migrations') IS NOT NULL AS ledger, to_regclass('shared.customers') IS NOT NULL AS customers`)
    if (!table.rows[0].ledger || !table.rows[0].customers) throw new Error('Migration baseline verification failed.')
    const baseline = await client.query(`SELECT 1 FROM website.payload_migrations WHERE name = $1 AND batch >= 0`, ['20261030_163225_baseline'])
    if (!baseline.rowCount) throw new Error('Migration baseline verification failed.')
  }
  console.log(`Preview ${task} completed.`)
} catch (error) {
  // Avoid logging database connection strings or credentials from underlying errors.
  console.error(task === 'migrate' ? 'Preview migration failed; inspect locally with redaction.' : 'Preview seed failed; inspect locally with redaction.')
  if (error instanceof Error && /^(Another preview|Existing untracked|Development schema|Baseline migration|Baseline is recorded|Migration baseline|Run migration|migrate failed|seed failed)/.test(error.message)) console.error(error.message)
  process.exitCode = 1
} finally { await client.end().catch(() => {}) }
