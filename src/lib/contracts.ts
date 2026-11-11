/**
 * The contract between the CMS and the interface.
 *
 * Rule of the codebase: components never see a Payload document. A page reads
 * the document on the server, maps it to one of the view models below, and
 * passes that down. This keeps the presentation layer independent of the CMS
 * schema, makes the "future platform module" a drop-in source of the same
 * models, and means a schema change is felt in exactly one mapping function.
 *
 * `src/payload-types.ts` is generated and may change at any time; only this file
 * and `src/lib/content.ts` are allowed to depend on it.
 */
import type { Page, Service } from '@/payload-types'

/** Rich text stays a CMS document; only its rendering crosses the boundary. */
export type RichTextDocument = NonNullable<Page['content'] | Service['content']>

/** A service as the interface knows it. */
export type ServiceCardModel = {
  id: string | number
  slug: string
  title: string
  summary: string
  /** Not open for requests yet: listed, but no call to action. */
  comingSoon: boolean
}

/** A service detail page. */
export type ServiceDetailModel = {
  slug: string
  title: string
  summary: string
  comingSoon: boolean
  cta: string
  content: RichTextDocument | null
}

/** One entry of the founder's prior experience. */
export type TrackRecordItemModel = {
  id: string | number
  title: string
  role: string | null
  description: string | null
}

/** One person on the team page. */
export type TeamMemberModel = {
  id: string | number
  name: string
  biography: string | null
}
