import { notFound } from 'next/navigation'
import { PlaceholderPage } from '@/components/site'

const pages: Record<string, Record<string, string>> = {
  company: { about: 'درباره ما', team: 'تیم' },
  services: {
    'industrial-electrical-consulting': 'مشاورهٔ فنی برق صنعتی',
    'building-electrical-design': 'طراحی برق ساختمان',
    'distribution-supervision': 'نظارت بر پروژه‌های توزیع',
    'energy-audit': 'ممیزی انرژی',
    'grounding-lightning-protection': 'طراحی سیستم ارت و صاعقه‌گیر',
    'technical-training': 'آموزش فنی (کارگاه) — به‌زودی',
  },
}

export default async function Detail({ params }: { params: Promise<{ section: string; item: string }> }) {
  const { section, item } = await params
  const title = pages[section]?.[item]
  if (!title) notFound()
  return <PlaceholderPage title={title} />
}
