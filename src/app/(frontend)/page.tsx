import type { Metadata } from 'next'
import { ContactBand, Founder, Hero, Platform, Principles, Services } from '@/components/home/sections'
import { getPage, getServiceCards } from '@/lib/content'
import { buildHomeContent, extractBlocks, type HomeService } from '@/lib/home-content'
import { pageMetadata } from '@/lib/seo'
import { notFound } from 'next/navigation'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = pageMetadata({
  title: 'Xennic | مهندسی برق، انرژی و اتوماسیون',
  description:
    'زر نور نیرو یکتا (Xennic): مشاوره، طراحی، نظارت و آموزش تخصصی در مهندسی برق قدرت، تأسیسات، انرژی و اتوماسیون.',
  path: '/',
})

export default async function Home() {
  const [page, services, about, trackRecord] = await Promise.all([
    getPage('home'),
    getServiceCards(),
    getPage('about'),
    getPage('track-record-intro'),
  ])
  if (!page) notFound()

  const content = buildHomeContent({
    pageTitle: page.title,
    pageSummary: page.summary ?? '',
    blocks: extractBlocks(page.content),
    aboutBlocks: extractBlocks(about?.content),
    trackRecord: trackRecord ? { heading: trackRecord.title, summary: trackRecord.summary ?? '' } : undefined,
    services: services.map<HomeService>((service) => ({
      slug: service.slug,
      title: service.title,
      summary: service.summary ?? '',
      comingSoon: Boolean(service.comingSoon),
    })),
  })

  return (
    <>
      <Hero content={content.hero} />
      <Principles pillars={content.pillars} />
      <Services services={content.services} />
      <Founder founder={content.founder} />
      <Platform platform={content.platform} />
      <ContactBand contact={content.contact} />
    </>
  )
}
