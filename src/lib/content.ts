import { getPayload } from 'payload'
import config from '@payload-config'

export async function getPage(slug: string) {
  const payload = await getPayload({ config })
  const result = await payload.find({ collection: 'pages', where: { slug: { equals: slug } }, limit: 1, overrideAccess: false })
  return result.docs[0] ?? null
}

export async function getService(slug: string) {
  const payload = await getPayload({ config })
  const result = await payload.find({ collection: 'services', where: { slug: { equals: slug } }, limit: 1, overrideAccess: false })
  return result.docs[0] ?? null
}

export async function getServices() {
  const payload = await getPayload({ config })
  return (await payload.find({ collection: 'services', sort: 'createdAt', limit: 100, overrideAccess: false })).docs
}

export async function getTrackRecord() {
  const payload = await getPayload({ config })
  return (await payload.find({ collection: 'track-record-items', sort: 'createdAt', limit: 100, overrideAccess: false })).docs
}

export async function getTeam() {
  const payload = await getPayload({ config })
  return (await payload.find({ collection: 'team-members', sort: 'createdAt', limit: 100, overrideAccess: false })).docs
}
