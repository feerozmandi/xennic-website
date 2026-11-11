import type { Metadata } from 'next'
import Image from 'next/image'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { BlockContent, ContentPage, NotPublished } from '@/components/content'
import { FOUNDER_PORTRAIT } from '@/lib/contact'
import { getDictionary, localeHref } from '@/lib/i18n'
import { en, englishServiceDetail, englishSectionMeta, englishTeam } from '@/lib/i18n-content'
import { pageMetadata } from '@/lib/seo'

export const dynamic = 'force-static'

const dict = getDictionary('en')

export function generateStaticParams() {
  return [
    ...en.services.map((service) => ({ section: 'services', item: service.slug })),
    { section: 'company', item: 'team' },
  ]
}

export async function generateMetadata({ params }: { params: Promise<{ section: string; item: string }> }): Promise<Metadata> {
  const { section, item } = await params
  if (section === 'services') {
    const service = englishServiceDetail(item)
    if (!service) return {}
    return pageMetadata({
      title: service.title,
      description: service.summary,
      path: `/en/services/${item}`,
      locale: 'en',
      // A service that is not open for requests yet is listed but not indexed.
      noindex: service.comingSoon,
    })
  }
  if (section === 'company' && item === 'team') {
    return pageMetadata({
      title: dict.content.teamTitle,
      description: 'The founder of Xennic and his professional record.',
      path: '/en/company/team',
      locale: 'en',
    })
  }
  return {}
}

export default async function EnglishDetail({ params }: { params: Promise<{ section: string; item: string }> }) {
  const { section, item } = await params
  const home = { href: localeHref('en', '/'), label: dict.home }

  if (section === 'services') {
    const service = englishServiceDetail(item)
    if (!service) notFound()
    return (
      <ContentPage
        locale="en"
        title={service.title}
        eyebrow={service.comingSoon ? dict.comingSoon : dict.content.serviceEyebrow}
        lead={service.summary}
        trail={[home, { href: localeHref('en', '/services'), label: englishSectionMeta.services.title }, { label: service.title }]}
      >
        <div className="prose-layout">
          <div className="prose-main">
            <BlockContent blocks={service.blocks} />
          </div>
          <aside className="page-aside page-aside--sticky" aria-label={dict.actions}>
            <h2 className="h3">{dict.content.serviceAsideTitle}</h2>
            {service.comingSoon ? (
              <>
                <p>{dict.content.serviceSoonText}</p>
                <span className="badge">{dict.comingSoon}</span>
              </>
            ) : (
              <>
                <p>{dict.content.serviceAsideText}</p>
                <Link className="btn btn--primary" href={localeHref('en', '/contact')}>
                  <span>{service.cta}</span>
                  <span className="btn__arrow" aria-hidden="true">←</span>
                </Link>
              </>
            )}
            <Link className="text-link" href={localeHref('en', '/services')}>
              {dict.content.allServices} <span className="arrow" aria-hidden="true">←</span>
            </Link>
          </aside>
        </div>
      </ContentPage>
    )
  }

  if (section === 'company' && item === 'team') {
    const members = englishTeam()
    if (members.length === 0) {
      return (
        <ContentPage locale="en" title={dict.content.teamTitle} trail={[home, { label: dict.content.teamTitle }]}>
          <NotPublished title={dict.content.teamTitle} note={dict.teamEmpty} locale="en" />
        </ContentPage>
      )
    }
    return (
      <ContentPage
        locale="en"
        title={dict.content.teamTitle}
        eyebrow={dict.content.teamEyebrow}
        lead={dict.content.teamLead}
        trail={[home, { label: englishSectionMeta.company.title }, { label: dict.content.teamTitle }]}
      >
        <ul className="team-list">
          {members.map((member) => (
            <li key={member.id} className="team-card glass glass--quiet">
              <Image
                className="team-card__photo"
                src={FOUNDER_PORTRAIT.src}
                width={FOUNDER_PORTRAIT.width}
                height={FOUNDER_PORTRAIT.height}
                alt={`Portrait of ${member.name}, founder of Xennic`}
                sizes="(max-width: 700px) 120px, 168px"
              />
              <div className="team-card__body">
                <h2 className="h3">{member.name}</h2>
                {member.biography && <p>{member.biography}</p>}
                <Link className="text-link" href={localeHref('en', '/track-record')}>
                  {dict.content.teamRecordLink} <span className="arrow" aria-hidden="true">←</span>
                </Link>
              </div>
            </li>
          ))}
        </ul>
      </ContentPage>
    )
  }

  notFound()
}
