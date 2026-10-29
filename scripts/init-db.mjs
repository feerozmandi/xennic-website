import { readFile } from 'node:fs/promises'
import { Client } from 'pg'

if (!process.env.DATABASE_URL) throw new Error('DATABASE_URL must be set in .env')
const client = new Client({ connectionString: process.env.DATABASE_URL })
try {
  await client.connect()
  await client.query('BEGIN')
  for (const migration of ['001-init.sql', '002-align-customers.sql']) {
    await client.query(await readFile(new URL(`../migrations/${migration}`, import.meta.url), 'utf8'))
  }
  await client.query('COMMIT')
  console.log('Development schemas and shared customer table are ready.')
} finally {
  await client.end()
}
