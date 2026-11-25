import type { Metadata } from 'next'
import { DeclarePlatformIsland } from '@/components/platform/declare-platform-island'
import { Breadcrumb } from '@/components/content'
import { Container, Eyebrow } from '@/components/ui/primitives'
import { JsonLd } from '@/components/ui/json-ld'
import { getDictionary } from '@/lib/i18n'
import { platformTools } from '@/lib/platform-content'
import { breadcrumbStructuredData, softwareApplicationLd } from '@/lib/structured-data'
import { pageMetadata } from '@/lib/seo'

export const metadata: Metadata = pageMetadata({
  title: 'Xennic Platform — engineering calculators',
  description:
    'Three Xennic calculators: capacitor bank sizing and power factor correction, a solar plant estimate, and a first energy-audit and earthing triage.',
  path: '/en/platform',
  locale: 'en',
})

const dict = getDictionary('en')

/**
 * The English edition of the platform page.
 *
 * It boots the same island — a Declare program is one artifact, not one per
 * language — so the frame is translated while the calculators' own interface
 * stays Persian, and the lead says so before a reader meets the panel.
 */
export default function EnglishPlatformPage() {
  return (
    <Container>
      <div className="page">
        <Breadcrumb locale="en" trail={[{ href: '/en', label: dict.home }, { label: 'Xennic Platform' }]} />

        <header className="page-heading">
          <Eyebrow>{dict.platformPage.eyebrow}</Eyebrow>
          <h1 className="h1">{dict.platformPage.title}</h1>
          <p className="lede">{dict.platformPage.lead}</p>
        </header>

        <section className="section section--tight" aria-labelledby="platform-tools-title">
          <h2 className="h2" id="platform-tools-title">{dict.platformPage.toolsTitle}</h2>
          <ul className="tool-list">
            {platformTools('en').map((tool) => (
              <li key={tool.title} className="tool-list__item">
                <h3 className="h3">{tool.title}</h3>
                <p>{tool.detail}</p>
                <p className="tool-list__inputs">
                  <span>{dict.platformPage.inputsLabel}</span> {tool.inputs}
                </p>
              </li>
            ))}
          </ul>
        </section>

        <section className="section" aria-labelledby="platform-island-title">
          <h2 className="h2" id="platform-island-title">{dict.platformPage.islandTitle}</h2>
          <p className="lede">{dict.platformPage.islandLead}</p>
          <DeclarePlatformIsland locale="en" />
        </section>
      </div>

      <JsonLd
        data={[
          breadcrumbStructuredData([{ name: 'Xennic Platform', path: '/en/platform' }], dict.home),
          softwareApplicationLd(),
        ]}
      />
    </Container>
  )
}
