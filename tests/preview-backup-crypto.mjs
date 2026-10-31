import { randomBytes } from 'node:crypto'
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'
import { decryptBackup, encryptBackup } from '../scripts/preview-backup-crypto.mjs'

test('authenticated backup roundtrip and fail-closed corruption', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'xennic-backup-crypto-test-'))
  const key = randomBytes(32)
  const otherKey = randomBytes(32)
  try {
    const input = join(dir, 'source')
    const encrypted = join(dir, 'encrypted')
    const restored = join(dir, 'restored')
    const plain = Buffer.concat([Buffer.from('synthetic fixture only'), randomBytes(65536)])
    await writeFile(input, plain, { mode: 0o600 })
    await encryptBackup(input, encrypted, key, 'database')
    assert.notDeepEqual(await readFile(encrypted), plain)
    await decryptBackup(encrypted, restored, key, 'database')
    assert.deepEqual(await readFile(restored), plain)
    await assert.rejects(encryptBackup(input, encrypted, key, 'database'))
    await assert.rejects(decryptBackup(encrypted, join(dir, 'wrong-key'), otherKey, 'database'))
    await assert.rejects(decryptBackup(encrypted, join(dir, 'wrong-type'), key, 'media'))
    const damaged = await readFile(encrypted)
    damaged[Math.floor(damaged.length / 2)] ^= 1
    await writeFile(join(dir, 'damaged'), damaged)
    await assert.rejects(decryptBackup(join(dir, 'damaged'), join(dir, 'damaged-output'), key, 'database'))
    await writeFile(join(dir, 'truncated'), damaged.subarray(0, 10))
    await assert.rejects(decryptBackup(join(dir, 'truncated'), join(dir, 'truncated-output'), key, 'database'))
    const names = await readdir(dir)
    for (const bad of ['wrong-key', 'wrong-type', 'damaged-output', 'truncated-output']) assert.ok(!names.includes(bad))
    assert.ok(!names.some((name) => name.includes('.tmp-')))
  } finally {
    key.fill(0); otherKey.fill(0)
    await rm(dir, { recursive: true, force: true })
  }
})
