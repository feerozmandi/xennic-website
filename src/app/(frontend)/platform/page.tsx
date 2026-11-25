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
  title: 'Xennic Platform — محاسبه‌گرهای مهندسی برق',
  description:
    'سه ابزار محاسباتی Xennic: ظرفیت بانک خازنی و اصلاح ضریب توان، تخمین فنی نیروگاه خورشیدی، و ارزیابی اولیهٔ ممیزی انرژی و ارتینگ.',
  path: '/platform',
})

const dict = getDictionary('fa')

/**
 * The platform page.
 *
 * The page itself is server-rendered text, so the tools are described and
 * indexable without the program ever running. The calculators load underneath
 * it in a Declare island (`DeclarePlatformIsland`), which is why this route is
 * in the sitemap: what a crawler gets is this copy, not an empty box.
 */
export default function PlatformPage() {
  return (
    <Container>
      <div className="page">
        <Breadcrumb trail={[{ href: '/', label: dict.home }, { label: 'Xennic Platform' }]} />

        <header className="page-heading">
          <Eyebrow>{dict.platformPage.eyebrow}</Eyebrow>
          <h1 className="h1">{dict.platformPage.title}</h1>
          <p className="lede">{dict.platformPage.lead}</p>
        </header>

        <section className="section section--tight" aria-labelledby="platform-tools-title">
          <h2 className="h2" id="platform-tools-title">{dict.platformPage.toolsTitle}</h2>
          <ul className="tool-list">
            {platformTools('fa').map((tool) => (
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
          <DeclarePlatformIsland />
        </section>
      </div>

      <JsonLd
        data={[
          breadcrumbStructuredData([{ name: 'Xennic Platform', path: '/platform' }], dict.home),
          softwareApplicationLd(),
        ]}
      />
    </Container>
  )
}
