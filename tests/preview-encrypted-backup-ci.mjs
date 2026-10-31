// Disposable synthetic CI fixture only. Never accepts production backup material.
import { randomBytes } from 'node:crypto'
import { readFile, rm, writeFile } from 'node:fs/promises'
import { isAbsolute, join, relative, resolve } from 'node:path'
import { decryptBackup, encryptBackup } from '../scripts/preview-backup-crypto.mjs'

if (process.env.CI !== 'true' || process.env.COMPOSE_PROJECT_NAME !== 'xennic-preview-ci') {
  throw new Error('Refusing: requires disposable preview CI project')
}
const scratch = process.argv[2]
const temp = process.env.RUNNER_TEMP
if (!scratch || !temp || !isAbsolute(scratch) || !isAbsolute(temp) ||
    !relative(resolve(temp), resolve(scratch)).startsWith('xennic-restore.')) {
  throw new Error('Refusing: unexpected CI scratch directory')
}
const key = randomBytes(32) // synthetic key; never written to disk or printed
try {
  for (const [source, encrypted, restored, kind] of [
    ['db.dump', 'db.enc', 'db.restored', 'database'],
    ['media.tar.gz', 'media.enc', 'media.restored', 'media'],
  ]) {
    await encryptBackup(join(scratch, source), join(scratch, encrypted), key, kind)
    await decryptBackup(join(scratch, encrypted), join(scratch, restored), key, kind)
    const before = await readFile(join(scratch, source))
    const after = await readFile(join(scratch, restored))
    if (!before.equals(after)) throw new Error('Synthetic encrypted backup roundtrip mismatch')
  }
  const broken = await readFile(join(scratch, 'db.enc'))
  broken[Math.floor(broken.length / 2)] ^= 1
  await writeFile(join(scratch, 'db-tampered.enc'), broken, { mode: 0o600 })
  let rejected = false
  try { await decryptBackup(join(scratch, 'db-tampered.enc'), join(scratch, 'must-not-exist'), key, 'database') }
  catch { rejected = true }
  if (!rejected) throw new Error('Tampered synthetic backup was not rejected')
  try { await readFile(join(scratch, 'must-not-exist')); throw new Error('Unauthenticated output was published') }
  catch (error) { if (error.code !== 'ENOENT') throw error }
  console.log('PASS: synthetic DB and media encrypted, authenticated and decrypted; tampering rejected')
} finally {
  key.fill(0)
  await rm(join(scratch, 'db-tampered.enc'), { force: true })
}
