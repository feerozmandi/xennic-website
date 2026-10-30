import Link from 'next/link'
import { notFound } from 'next/navigation'
import { ContentPage, DocumentContent, ServiceCards } from '@/components/content'
import { PlaceholderPage } from '@/components/site'
import { getPage, getServices, getTrackRecord } from '@/lib/content'

export const dynamic = 'force-dynamic'
const placeholders: Record<string, string> = {
  knowledge: 'دانشنامه', tools: 'ابزارهای مهندسی', platform: 'Xennic Platform — به‌زودی',
  contact: 'تماس با ما', privacy: 'حریم خصوصی', terms: 'شرایط استفاده', cookies: 'کوکی‌ها',
}

export default async function Section({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params
  if (section === 'company') {
    const page = await getPage('about')
    if (!page) notFound()
    return <ContentPage title={page.title}><DocumentContent content={page.content} /><Link href="/company/team">تیم</Link></ContentPage>
  }
  if (section === 'services') return <ContentPage title="خدمات"><ServiceCards services={await getServices()} /></ContentPage>
  if (section === 'track-record') return <ContentPage title="تجربه و پیشینهٔ مهندسی">
    <div className="cards">{(await getTrackRecord()).map((item) => <article className="card" key={item.id}>
      <span className="badge">پیش از تأسیس Xennic</span><h2>{item.title}</h2>
      {item.role && <p>{item.role}</p>}{item.description && <p>{item.description}</p>}
    </article>)}</div>
  </ContentPage>
  const title = placeholders[section]
  if (!title) notFound()
  return <PlaceholderPage title={title} />
}
