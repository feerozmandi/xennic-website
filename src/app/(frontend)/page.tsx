import Link from 'next/link'
import { notFound } from 'next/navigation'
import { DocumentContent, ServiceCards } from '@/components/content'
import { getPage, getServices } from '@/lib/content'

export const dynamic = 'force-dynamic'

export default async function Home() {
  const [page, services, trackRecordIntro] = await Promise.all([getPage('home'), getServices(), getPage('track-record-intro')])
  if (!page) notFound()
  return <>
    <section className="hero"><div className="container hero-content">
      <h1>{page.title}</h1>{page.summary && <p>{page.summary}</p>}
      <div className="hero-actions"><button className="button" type="button" disabled>درخواست مشاوره مهندسی</button><Link className="button" href="/services">آشنایی با خدمات</Link></div>
    </div></section>
    <section className="container page-section"><h2>چرا Xennic؟</h2><DocumentContent content={page.content} /></section>
    <section className="surface-muted"><div className="container page-section"><h2>خدمات راهبردی</h2><ServiceCards services={services} /></div></section>
    <section className="container page-section" data-testid="track-record-intro"><h2>تجربهٔ مهندسی که می‌توان به آن اعتماد کرد</h2>{trackRecordIntro?.summary && <p>{trackRecordIntro.summary}</p>}<Link href="/track-record">مشاهدهٔ پیشینهٔ مهندسی</Link></section>
    <section className="container page-section" data-testid="platform-intro"><h2>Xennic Platform</h2><span className="badge">به‌زودی</span></section>
  </>
}
