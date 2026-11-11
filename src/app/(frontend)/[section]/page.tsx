import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { ContentPage, DocumentContent, NotPublished, ServiceCards, TrackRecordList } from '@/components/content'
import { getPage, getServices, getTrackRecord } from '@/lib/content'
import { pageMetadata } from '@/lib/seo'

export const dynamic = 'force-dynamic'

/**
 * Each section owns its title, description and canonical. Sections that are
 * linked but not published are served with `noindex` instead of being hidden,
 * so visitors are not dead-ended and search engines keep them out.
 */
const sectionMeta: Record<string, { title: string; description: string }> = {
  company: {
    title: 'درباره ما',
    description: 'زر نور نیرو یکتا (Xennic): مأموریت، چشم‌انداز و اصول کاری در مهندسی برق قدرت، انرژی و اتوماسیون.',
  },
  services: {
    title: 'خدمات',
    description: 'مشاورهٔ برق صنعتی، طراحی برق ساختمان، نظارت بر توزیع، ممیزی انرژی، ارت و صاعقه‌گیر و آموزش فنی.',
  },
  'track-record': {
    title: 'پیشینهٔ مهندسی',
    description: 'تجربهٔ عملی مؤسس Xennic در شبکهٔ توزیع و پروژه‌های برق، پیش از تأسیس این مجموعه.',
  },
  knowledge: { title: 'دانشنامه', description: 'دانشنامهٔ فنی Xennic؛ در حال آماده‌سازی.' },
  tools: { title: 'ابزارهای مهندسی', description: 'ابزارهای مهندسی Xennic؛ در حال آماده‌سازی.' },
  platform: { title: 'Xennic Platform', description: 'پلتفرم مهندسی Xennic؛ در حال آماده‌سازی.' },
  privacy: { title: 'حریم خصوصی', description: 'سیاست حریم خصوصی Xennic؛ در حال آماده‌سازی.' },
  terms: { title: 'شرایط استفاده', description: 'شرایط استفاده از وب‌سایت Xennic؛ در حال آماده‌سازی.' },
  cookies: { title: 'کوکی‌ها', description: 'سیاست کوکی وب‌سایت Xennic؛ در حال آماده‌سازی.' },
}

/** Sections whose content is not approved yet must not be indexed. */
const unpublished = new Set(['knowledge', 'tools', 'platform', 'privacy', 'terms', 'cookies'])

export async function generateMetadata({ params }: { params: Promise<{ section: string }> }): Promise<Metadata> {
  const { section } = await params
  const meta = sectionMeta[section]
  if (!meta) return {}
  return pageMetadata({ ...meta, path: `/${section}`, noindex: unpublished.has(section) })
}

/** Pages that appear in navigation but have no approved content yet. */
const notPublished: Record<string, string> = {
  knowledge: 'دانشنامه',
  tools: 'ابزارهای مهندسی',
  platform: 'Xennic Platform',
  privacy: 'حریم خصوصی',
  terms: 'شرایط استفاده',
  cookies: 'کوکی‌ها',
}

export default async function Section({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params

  if (section === 'company') {
    const page = await getPage('about')
    if (!page) notFound()
    return (
      <ContentPage
        title={page.title}
        eyebrow="دربارهٔ شرکت"
        lead={page.summary ?? undefined}
        trail={[{ href: '/', label: 'خانه' }, { label: page.title }]}
      >
        <div className="prose-layout">
          <DocumentContent content={page.content} />
          <aside className="page-aside" aria-label="دسترسی بیشتر">
            <h2 className="h3">تیم و مؤسس</h2>
            <p>معرفی مؤسس و سابقهٔ حرفه‌ای ایشان، جدا از سابقهٔ شرکت.</p>
            <Link className="text-link" href="/company/team">
              تیم <span aria-hidden="true">←</span>
            </Link>
            <Link className="text-link" href="/track-record">
              پیشینهٔ مهندسی <span aria-hidden="true">←</span>
            </Link>
            <Link className="text-link" href="/services">
              خدمات <span aria-hidden="true">←</span>
            </Link>
          </aside>
        </div>
      </ContentPage>
    )
  }

  if (section === 'services') {
    return (
      <ContentPage
        title="خدمات"
        eyebrow="دامنهٔ خدمات"
        lead="خدمات در حوزهٔ برق قدرت، تأسیسات، انرژی و آموزش تخصصی؛ هر خدمت با دامنهٔ مشخص و خروجی قابل استناد."
        trail={[{ href: '/', label: 'خانه' }, { label: 'خدمات' }]}
      >
        <ServiceCards services={await getServices()} />
      </ContentPage>
    )
  }

  if (section === 'track-record') {
    const items = await getTrackRecord()
    return (
      <ContentPage
        title="تجربه و پیشینهٔ مهندسی"
        eyebrow="پیشینهٔ مؤسس"
        lead="تجربهٔ عملی مؤسس Xennic در شبکهٔ توزیع و پروژه‌های برق، پیش از تأسیس این مجموعه."
        trail={[{ href: '/', label: 'خانه' }, { label: 'پیشینهٔ مهندسی' }]}
      >
        <TrackRecordList items={items} />
      </ContentPage>
    )
  }

  const title = notPublished[section]
  if (!title) notFound()
  return (
    <ContentPage title={title} trail={[{ href: '/', label: 'خانه' }, { label: title }]}>
      <NotPublished title={title} />
    </ContentPage>
  )
}
