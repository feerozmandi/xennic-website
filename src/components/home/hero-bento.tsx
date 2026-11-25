import Link from 'next/link'
import { getDictionary, localeHref, type Locale } from '@/lib/i18n'
import { BENTO_FIGURES, type HomeContent } from '@/lib/home-content'
import { Container } from '../ui/primitives'
import { SingleLineDiagram } from './single-line-diagram'

/**
 * The first screen: a Bento grid of glass panels.
 *
 * Four panels, all above the fold on a desktop and in reading order on a
 * phone:
 *
 * 1. the brand message with both calls to action,
 * 2. the living single-line diagram,
 * 3. `+ ۴ دهه` — the founder's practical experience,
 * 4. `IEC / مبحث ۱۳` — the standards the design work is measured against,
 * 5. `۷ حوزه` — the number of approved service areas,
 * 6. `Xennic AI` — the analysis layer, with the one honest status there is.
 *
 * There is no slider. Every figure is a fact from an approved source, and the
 * fourth one links to the Platform section instead of promising a product that
 * is not published yet.
 */
export function BentoHero({ content, locale = 'fa' }: { content: HomeContent['hero']; locale?: Locale }) {
  const dict = getDictionary(locale)
  const figures = BENTO_FIGURES(locale)

  return (
    <section className="bento-hero" aria-labelledby="hero-title">
      <Container>
        <div className="bento-hero__grid">
          <div className="glass bento-hero__copy" data-reveal>
            <span className="bento-hero__eyebrow">{content.eyebrow}</span>
            <h1 id="hero-title" className="bento-hero__title">{content.title}</h1>
            {content.summary && <p className="bento-hero__summary">{content.summary}</p>}
            <div className="bento-hero__actions">
              <Link className="btn btn--primary" href={localeHref(locale, '/contact')}>
                <span>{dict.hero.primaryCta}</span>
                <span className="btn__arrow" aria-hidden="true">←</span>
              </Link>
              <Link className="btn btn--glass" href={localeHref(locale, '/platform')}>
                <span>{dict.hero.platformCta}</span>
                <span className="btn__arrow" aria-hidden="true">←</span>
              </Link>
            </div>
            <p className="bento-hero__note">{dict.hero.diagramNote}</p>
          </div>

          <div className="glass bento-hero__art" data-reveal>
            <SingleLineDiagram locale={locale} />
          </div>

          <ul className="bento-hero__figures" aria-label={dict.hero.figuresLabel}>
            {figures.map((figure) => (
              <li key={figure.id} className="glass bento-hero__figure" data-reveal>
                <strong>{figure.value}</strong>
                <span>
                  {figure.href ? (
                    <Link href={localeHref(locale, figure.href)}>{figure.label}</Link>
                  ) : (
                    figure.label
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </Container>
    </section>
  )
}
