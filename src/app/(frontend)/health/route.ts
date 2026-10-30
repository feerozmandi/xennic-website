import { Client } from 'pg'

export const dynamic = 'force-dynamic'
export async function GET() {
  const db = new Client({ connectionString: process.env.DATABASE_URL, connectionTimeoutMillis: 2000 })
  try {
    await db.connect()
    await db.query('SELECT 1')
    return Response.json({ status: 'ok' }, { headers: { 'Cache-Control': 'no-store' } })
  } catch {
    return Response.json({ status: 'unavailable' }, { status: 503, headers: { 'Cache-Control': 'no-store' } })
  } finally { await db.end().catch(() => {}) }
}
