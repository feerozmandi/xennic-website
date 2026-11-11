import type { Metadata } from 'next'
import Image from 'next/image'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { ContentPage, DocumentContent, NotPublished } from '@/components/content'
import { FOUNDER_PORTRAIT } from '@/lib/contact'
import { getPage, getServiceDetail, getTeamMembers } from '@/lib/content'
import { FOUNDER_NAME } from '@/lib/home-content'
import { pageMetadata } from '@/lib/seo'

export const dynamic = 'force-dynamic'

export async function generateMetadata({ params }: { params: Promise<{ section: string; item: string }> }): Promise<Metadata> {
  const { section, item } = await params
  if (section === 'services') {
    const service = await getServiceDetail(item)
    if (!service) return {}
    return pageMetadata({
      title: service.title,
      description: service.summary ?? service.title,
      path: `/services/${item}`,
      // A service that is not open for requests yet is listed but not indexed.
      noindex: Boolean(service.comingSoon),
    })
  }
  if (section === 'company' && item === 'team') {
    return pageMetadata({
      title: 'تیم',
      description: 'معرفی مؤسس Xennic و سابقهٔ حرفه‌ای ایشان.',
      path: '/company/team',
    })
  }
  if (section === 'company' && item === 'about') {
    return pageMetadata({ title: 'درباره ما', description: 'دربارهٔ زر نور نیرو یکتا (Xennic).', path: '/company/about' })
  }
  return {}
}

export default async function Detail({ params }: { params: Promise<{ section: string; item: string }> }) {
  const { section, item } = await params

  if (section === 'services') {
    const service = await getServiceDetail(item)
    if (!service) notFound()
    const cta = service.comingSoon ? null : service.cta
    return (
      <ContentPage
        title={service.title}
        eyebrow={service.comingSoon ? 'به‌زودی' : 'خدمت'}
        lead={service.summary ?? undefined}
        trail={[{ href: '/', label: 'خانه' }, { href: '/services', label: 'خدمات' }, { label: service.title }]}
      >
        <div className="prose-layout">
          <div className="prose-main">
            <DocumentContent content={service.content} />
          </div>
          <aside className="page-aside page-aside--sticky" aria-label="اقدام">
            <h2 className="h3">گفت‌وگو دربارهٔ این خدمت</h2>
            {service.comingSoon ? (
              <>
                <p>این خدمت هنوز برای درخواست باز نشده است.</p>
                <span className="badge">به‌زودی</span>
              </>
            ) : (
              <>
                <p>برای بررسی دامنهٔ کار و زمان‌بندی، از مسیرهای تماس استفاده کنید یا فرم درخواست را پر کنید.</p>
                <Link className="btn btn--primary" href="/contact">
                  <span>{cta}</span>
                  <span className="btn__arrow" aria-hidden="true">←</span>
                </Link>
              </>
            )}
            <Link className="text-link" href="/services">
              همهٔ خدمات <span aria-hidden="true">←</span>
            </Link>
          </aside>
        </div>
      </ContentPage>
    )
  }

  if (section === 'company' && item === 'about') {
    const page = await getPage('about')
    if (!page) notFound()
    return (
      <ContentPage
        title={page.title}
        trail={[{ href: '/', label: 'خانه' }, { href: '/company', label: 'شرکت' }, { label: page.title }]}
      >
        <DocumentContent content={page.content} />
      </ContentPage>
    )
  }

  if (section === 'company' && item === 'team') {
    const members = await getTeamMembers()
    if (members.length === 0) return (
      <ContentPage title="تیم" trail={[{ href: '/', label: 'خانه' }, { href: '/company', label: 'شرکت' }, { label: 'تیم' }]}>
        <NotPublished title="تیم" note="معرفی اعضای تیم پس از تأیید منتشر می‌شود." />
      </ContentPage>
    )
    return (
      <ContentPage
        title="تیم"
        eyebrow="افراد"
        lead="معرفی مؤسس و سابقهٔ حرفه‌ای ایشان؛ سابقهٔ پروژه‌های شرکت در بخش پیشینهٔ مهندسی آمده است."
        trail={[{ href: '/', label: 'خانه' }, { href: '/company', label: 'شرکت' }, { label: 'تیم' }]}
      >
        <ul className="team-list">
          {members.map((member) => (
            <li key={member.id} className="team-card glass glass--quiet">
              <Image
                className="team-card__photo"
                src={FOUNDER_PORTRAIT.src}
                width={FOUNDER_PORTRAIT.width}
                height={FOUNDER_PORTRAIT.height}
                alt={FOUNDER_PORTRAIT.alt}
                sizes="(max-width: 700px) 120px, 168px"
              />
              <div className="team-card__body">
                <h2 className="h3">{member.name || FOUNDER_NAME}</h2>
                {member.biography && <p>{member.biography}</p>}
                <Link className="text-link" href="/track-record">
                  پیشینهٔ حرفه‌ای <span aria-hidden="true">←</span>
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
