import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { BlockContent, ContentPage, NotPublished, ServiceCards, TrackRecordList } from '@/components/content'
import { getDictionary, localeHref } from '@/lib/i18n'
import {
  en,
  englishNotPublished,
  englishSectionMeta,
  englishServiceCards,
  englishTrackRecord,
} from '@/lib/i18n-content'
import { FIELD_IMAGES } from '@/lib/imagery'
import { pageMetadata } from '@/lib/seo'

export const dynamic = 'force-static'

const dict = getDictionary('en')

/** Same split as the Persian tree: linked but unpublished pages are `noindex`. */
const unpublished = new Set(Object.keys(englishNotPublished))

export function generateStaticParams() {
  return ['company', 'services', 'track-record', ...Object.keys(englishNotPublished)].map((section) => ({ section }))
}

export async function generateMetadata({ params }: { params: Promise<{ section: string }> }): Promise<Metadata> {
  const { section } = await params
  const meta = englishSectionMeta[section]
  if (!meta) return {}
  return pageMetadata({
    title: meta.title,
    description: meta.description,
    path: `/en/${section}`,
    locale: 'en',
    noindex: unpublished.has(section),
  })
}

export default async function EnglishSection({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params
  const home = { href: localeHref('en', '/'), label: dict.home }

  if (section === 'company') {
    return (
      <ContentPage
        locale="en"
        title={englishSectionMeta.company.title}
        eyebrow={dict.content.aboutEyebrow}
        lead={en.aboutBlocks[0]?.text}
        trail={[home, { label: englishSectionMeta.company.title }]}
      >
        <div className="prose-layout">
          <BlockContent blocks={en.aboutBlocks} />
          <aside className="page-aside" aria-label={dict.more}>
            <h2 className="h3">{dict.content.aboutAsideTitle}</h2>
            <p>{dict.content.aboutAsideText}</p>
            <Link className="text-link" href={localeHref('en', '/company/team')}>
              {dict.content.team} <span className="arrow" aria-hidden="true">←</span>
            </Link>
            <Link className="text-link" href={localeHref('en', '/track-record')}>
              {dict.content.record} <span className="arrow" aria-hidden="true">←</span>
            </Link>
            <Link className="text-link" href={localeHref('en', '/services')}>
              {dict.content.services} <span className="arrow" aria-hidden="true">←</span>
            </Link>
          </aside>
        </div>
      </ContentPage>
    )
  }

  if (section === 'services') {
    return (
      <ContentPage
        locale="en"
        title={englishSectionMeta.services.title}
        eyebrow={dict.content.servicesEyebrow}
        lead={dict.content.servicesLead}
        trail={[home, { label: englishSectionMeta.services.title }]}
        media={FIELD_IMAGES.panels ?? undefined}
      >
        <ServiceCards services={englishServiceCards()} locale="en" />
      </ContentPage>
    )
  }

  if (section === 'track-record') {
    return (
      <ContentPage
        locale="en"
        title={dict.content.recordTitle}
        eyebrow={dict.content.recordEyebrow}
        lead={dict.content.recordLead}
        trail={[home, { label: englishSectionMeta['track-record'].title }]}
        media={FIELD_IMAGES.distribution ?? undefined}
      >
        <TrackRecordList items={englishTrackRecord()} locale="en" />
      </ContentPage>
    )
  }

  const title = englishNotPublished[section]
  if (!title) notFound()
  return (
    <ContentPage locale="en" title={title} trail={[home, { label: title }]}>
      <NotPublished title={title} locale="en" />
    </ContentPage>
  )
}
