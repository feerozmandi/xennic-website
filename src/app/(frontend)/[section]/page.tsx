import Link from 'next/link'
import { notFound } from 'next/navigation'
import { PlaceholderPage } from '@/components/site'

const sections: Record<string, string> = {
  company: 'شرکت', services: 'خدمات', 'track-record': 'تجربه و پیشینهٔ مهندسی',
  knowledge: 'دانشنامه', tools: 'ابزارهای مهندسی', platform: 'Xennic Platform — به‌زودی',
  contact: 'تماس با ما', privacy: 'حریم خصوصی', terms: 'شرایط استفاده', cookies: 'کوکی‌ها',
}
const services = [
  ['industrial-electrical-consulting', 'مشاورهٔ فنی برق صنعتی'],
  ['building-electrical-design', 'طراحی برق ساختمان'],
  ['distribution-supervision', 'نظارت بر پروژه‌های توزیع'],
  ['energy-audit', 'ممیزی انرژی'],
  ['grounding-lightning-protection', 'طراحی سیستم ارت و صاعقه‌گیر'],
  ['technical-training', 'آموزش فنی (کارگاه) — به‌زودی'],
]

export default async function Section({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params
  const title = sections[section]
  if (!title) notFound()
  return <PlaceholderPage title={title}>
    {section === 'services' && <ul className="page-list">{services.map(([slug, label]) => <li key={slug}><Link href={`/services/${slug}`}>{label}</Link></li>)}</ul>}
    {section === 'company' && <ul className="page-list"><li><Link href="/company/about">درباره ما</Link></li><li><Link href="/company/team">تیم</Link></li></ul>}
  </PlaceholderPage>
}
