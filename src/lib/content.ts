import { getPayload } from 'payload'
import config from '@payload-config'
import type {
  RichTextDocument,
  ServiceCardModel,
  ServiceDetailModel,
  TeamMemberModel,
  TrackRecordItemModel,
} from './contracts'

/**
 * The server side of the content layer.
 *
 * Everything that talks to Payload lives here, and everything it returns is a
 * view model from `contracts.ts` — never a raw document. Pages call these
 * functions; components receive the models as props.
 */

export async function getPageDocument(slug: string) {
  const payload = await getPayload({ config })
  const result = await payload.find({ collection: 'pages', where: { slug: { equals: slug } }, limit: 1, overrideAccess: false })
  return result.docs[0] ?? null
}

export async function getPage(slug: string) {
  const document = await getPageDocument(slug)
  if (!document) return null
  return {
    slug: document.slug,
    title: document.title,
    summary: document.summary ?? null,
    content: (document.content ?? null) as RichTextDocument | null,
  }
}

export async function getServiceDetail(slug: string): Promise<ServiceDetailModel | null> {
  const payload = await getPayload({ config })
  const result = await payload.find({ collection: 'services', where: { slug: { equals: slug } }, limit: 1, overrideAccess: false })
  const service = result.docs[0]
  if (!service) return null
  return {
    slug: service.slug,
    title: service.title,
    summary: service.summary ?? '',
    comingSoon: Boolean(service.comingSoon),
    cta: service.cta ?? 'درخواست مشاوره',
    content: (service.content ?? null) as RichTextDocument | null,
  }
}

export async function getServiceCards(): Promise<ServiceCardModel[]> {
  const payload = await getPayload({ config })
  const result = await payload.find({ collection: 'services', sort: 'createdAt', limit: 100, overrideAccess: false })
  return result.docs.map((service) => ({
    id: service.id,
    slug: service.slug,
    title: service.title,
    summary: service.summary ?? '',
    comingSoon: Boolean(service.comingSoon),
  }))
}

/** Published services only: used by the sitemap. */
export async function getPublishedServiceSlugs(): Promise<string[]> {
  const cards = await getServiceCards()
  return cards.filter((service) => !service.comingSoon).map((service) => service.slug)
}

export async function getServices() {
  return getServiceCards()
}

export async function getTrackRecordItems(): Promise<TrackRecordItemModel[]> {
  const payload = await getPayload({ config })
  const result = await payload.find({ collection: 'track-record-items', sort: 'createdAt', limit: 100, overrideAccess: false })
  return result.docs.map((item) => ({
    id: item.id,
    title: item.title,
    role: item.role ?? null,
    description: item.description ?? null,
  }))
}

export async function getTrackRecord() {
  return getTrackRecordItems()
}

export async function getTeamMembers(): Promise<TeamMemberModel[]> {
  const payload = await getPayload({ config })
  const result = await payload.find({ collection: 'team-members', sort: 'createdAt', limit: 100, overrideAccess: false })
  return result.docs.map((member) => ({
    id: member.id,
    name: member.name ?? '',
    biography: member.biography ?? null,
  }))
}

export async function getTeam() {
  return getTeamMembers()
}
