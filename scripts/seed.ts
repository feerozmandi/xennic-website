import { getPayload } from 'payload'
import config from '../src/payload.config'
import type { Page, Service } from '../src/payload-types'
import {
  FOUNDER_BIO,
  aboutPage,
  homePage,
  services as approvedServices,
  trackRecord as approvedTrackRecord,
  trackRecordIntroPage,
  type CopyBlock,
} from '../src/lib/approved-copy'

// Public copy lives in src/lib/approved-copy.ts (verbatim from L2-MKT-004 v0.2.1,
// Vault dev c51e087) so the seed and the design preview cannot diverge.
function richText(blocks: CopyBlock[]): NonNullable<Page['content']> {
  return {
    root: {
      type: 'root', direction: 'rtl', format: '', indent: 0, version: 1,
      children: blocks.flatMap(({ heading, text }) => [
        { type: 'heading', tag: 'h2', direction: 'rtl', format: '', indent: 0, version: 1, children: [{ type: 'text', text: heading, detail: 0, format: 0, mode: 'normal', style: '', version: 1 }] },
        { type: 'paragraph', direction: 'rtl', format: '', indent: 0, version: 1, textFormat: 0, textStyle: '', children: [{ type: 'text', text, detail: 0, format: 0, mode: 'normal', style: '', version: 1 }] },
      ]),
    },
  }
}

const pages: Array<Pick<Page, 'title' | 'slug' | 'summary' | 'content'>> = [
  { slug: trackRecordIntroPage.slug, title: trackRecordIntroPage.title, summary: trackRecordIntroPage.summary },
  { slug: homePage.slug, title: homePage.title, summary: homePage.summary, content: richText(homePage.blocks) },
  { slug: aboutPage.slug, title: aboutPage.title, content: richText(aboutPage.blocks) },
]

const services: Array<Pick<Service, 'title' | 'slug' | 'summary' | 'content' | 'cta' | 'comingSoon'>> =
  approvedServices.map(({ slug, title, summary, cta, comingSoon, blocks }) => ({
    slug, title, summary, cta, comingSoon, content: richText(blocks),
  }))

const trackRecord = approvedTrackRecord

async function main() {
  const payload = await getPayload({ config })
  try {
    for (const page of pages) {
      const existing = await payload.find({ collection: 'pages', where: { slug: { equals: page.slug } }, limit: 1 })
      if (!existing.totalDocs) await payload.create({ collection: 'pages', data: page })
    }
    for (const service of services) {
      const existing = await payload.find({ collection: 'services', where: { slug: { equals: service.slug } }, limit: 1 })
      if (!existing.totalDocs) await payload.create({ collection: 'services', data: service })
    }
    for (const item of trackRecord) {
      const existing = await payload.find({ collection: 'track-record-items', where: { title: { equals: item.title } }, limit: 1 })
      if (!existing.totalDocs) await payload.create({ collection: 'track-record-items', data: item })
    }
    const existing = await payload.find({ collection: 'team-members', where: { name: { equals: 'احمد فیروزمندی' } }, limit: 1 })
    if (!existing.totalDocs) await payload.create({ collection: 'team-members', data: { name: 'احمد فیروزمندی', biography: FOUNDER_BIO } })
    console.log('Approved seed complete. Existing records were not overwritten.')
  } finally {
    await payload.destroy()
  }
}

// Payload's PostgreSQL adapter retains a client; explicitly exit after completed writes.
main().then(() => process.exit(0)).catch(() => { console.error('Seed failed; inspect locally with redaction.'); process.exit(1) })
