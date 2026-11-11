import type { Metadata } from 'next'
import { ContactBand, Founder, Hero, Platform, Principles, Services } from '@/components/home/sections'
import { buildEnglishHomeContent } from '@/lib/i18n-content'
import { pageMetadata } from '@/lib/seo'

export const metadata: Metadata = pageMetadata({
  title: 'Xennic | Electrical, energy and automation engineering',
  description:
    'Zar-e Noor-e Niroo-e Yekta (Xennic): consultancy, design, supervision and specialist training in power, building services, energy and automation engineering.',
  path: '/en',
  locale: 'en',
})

/**
 * English home page.
 *
 * Same sections and the same claims as the Persian home page; the copy is the
 * reviewed translation in `i18n-content.ts`, so the English edition can be
 * updated without touching the CMS.
 */
export default function EnglishHome() {
  const content = buildEnglishHomeContent()
  return (
    <>
      <Hero content={content.hero} locale="en" />
      <Principles pillars={content.pillars} locale="en" />
      <Services services={content.services} locale="en" />
      <Founder founder={content.founder} locale="en" />
      <Platform platform={content.platform} locale="en" />
      <ContactBand contact={content.contact} />
    </>
  )
}
