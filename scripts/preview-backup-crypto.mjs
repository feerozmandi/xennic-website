// Experimental authenticated encryption primitive; not a production backup CLI.
// Callers MUST use private, trusted directories (0700), coordinate the snapshot,
// and provide approved key management/storage. Decryption writes unauthenticated
// plaintext to a 0600 temporary file there until the GCM tag has been checked.
import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto'
import { createReadStream, createWriteStream } from 'node:fs'
import { link, open, unlink } from 'node:fs/promises'
import { Readable } from 'node:stream'
import { pipeline } from 'node:stream/promises'

const MAGIC = Buffer.from('XNCB1')
const HEADER_SIZE = MAGIC.length + 1 + 12
const TAG_SIZE = 16
const TYPES = Object.freeze({ database: 1, media: 2 })

function validate(key, kind) {
  if (!Buffer.isBuffer(key) || key.length !== 32 || !Object.hasOwn(TYPES, kind)) {
    throw new Error('Invalid backup encryption parameters')
  }
}
function tempName(output) { return `${output}.tmp-${randomBytes(12).toString('hex')}` }
async function removeTemporary(path) {
  try { await unlink(path) } catch (error) { if (error.code !== 'ENOENT') throw error }
}
async function publish(temp, output) {
  // Atomic no-overwrite publication within the private destination directory.
  await link(temp, output)
  await unlink(temp)
}

export async function encryptBackup(input, output, key, kind) {
  validate(key, kind)
  const temporary = tempName(output)
  const nonce = randomBytes(12)
  const header = Buffer.concat([MAGIC, Buffer.from([TYPES[kind]]), nonce])
  let created = false
  let file
  let source
  try {
    source = await open(input, 'r')
    file = await open(temporary, 'wx', 0o600)
    created = true
    await file.writeFile(header)
    const cipher = createCipheriv('aes-256-gcm', key, nonce)
    cipher.setAAD(header)
    await pipeline(createReadStream(null, { fd: source.fd, autoClose: false }), cipher,
      createWriteStream(null, { fd: file.fd, start: HEADER_SIZE, autoClose: false }))
    const tag = cipher.getAuthTag()
    const offset = (await file.stat()).size
    const { bytesWritten } = await file.write(tag, 0, tag.length, offset)
    if (bytesWritten !== tag.length) throw new Error('Incomplete authentication tag write')
    await file.sync()
    await file.close(); file = undefined
    await publish(temporary, output)
    created = false
  } finally {
    try {
      if (source) await source.close().catch((error) => { if (error.code !== 'EBADF') throw error })
      if (file) await file.close().catch((error) => { if (error.code !== 'EBADF') throw error })
    } finally {
      if (created) await removeTemporary(temporary)
    }
  }
}

export async function decryptBackup(input, output, key, kind) {
  validate(key, kind)
  const temporary = tempName(output)
  const encrypted = await open(input, 'r')
  let created = false
  let file
  try {
    const { size } = await encrypted.stat()
    if (size < HEADER_SIZE + TAG_SIZE) throw new Error('Invalid encrypted backup')
    const header = Buffer.alloc(HEADER_SIZE)
    const tag = Buffer.alloc(TAG_SIZE)
    if ((await encrypted.read(header, 0, header.length, 0)).bytesRead !== header.length ||
        (await encrypted.read(tag, 0, tag.length, size - TAG_SIZE)).bytesRead !== tag.length ||
        !header.subarray(0, MAGIC.length).equals(MAGIC) || header[MAGIC.length] !== TYPES[kind]) {
      throw new Error('Invalid encrypted backup')
    }
    file = await open(temporary, 'wx', 0o600)
    created = true
    const decipher = createDecipheriv('aes-256-gcm', key, header.subarray(MAGIC.length + 1))
    decipher.setAAD(header)
    decipher.setAuthTag(tag)
    const ciphertext = size === HEADER_SIZE + TAG_SIZE
      ? Readable.from([])
      : createReadStream(null, { fd: encrypted.fd, start: HEADER_SIZE, end: size - TAG_SIZE - 1, autoClose: false })
    await pipeline(ciphertext, decipher, createWriteStream(null, { fd: file.fd, autoClose: false }))
    await file.sync()
    await file.close(); file = undefined
    await publish(temporary, output)
    created = false
  } finally {
    try {
      await encrypted.close().catch((error) => { if (error.code !== 'EBADF') throw error })
      if (file) await file.close().catch((error) => { if (error.code !== 'EBADF') throw error })
    } finally {
      if (created) await removeTemporary(temporary)
    }
  }
}
