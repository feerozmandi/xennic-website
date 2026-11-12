import Image from 'next/image'
import Link from 'next/link'
import { getDictionary, localeHref, type Locale } from '@/lib/i18n'
import { FOUNDER_PORTRAIT } from '@/lib/contact'
import { serviceImage } from '@/lib/imagery'
import { heroSlides } from '@/lib/hero-slides'
import { HeroCarousel } from './hero-carousel'
import { Action, Container, Eyebrow, SectionHeading } from '../ui/primitives'
import { faNumber, type HomeContent } from '../../lib/home-content'

const principleIndex = (index: number, locale: Locale) =>
  locale === 'en' ? String(index + 1).padStart(2, '0') : faNumber(index + 1).padStart(2, '۰')

/**
 * Home page sections.
 *
 * Each section receives its copy from the page (Persian from the CMS, English
 * from the reviewed translation) and takes the interface strings from the
 * dictionary, so the same markup renders both editions.
 */

export function Hero({ content, locale = 'fa' }: { content: HomeContent['hero']; locale?: Locale }) {
  return <HeroCarousel slides={heroSlides(locale)} facts={content.facts} locale={locale} />
}

export function Principles({ pillars, locale = 'fa' }: { pillars: HomeContent['pillars']; locale?: Locale }) {
  const dict = getDictionary(locale)
  return (
    <section className="section" aria-labelledby="principles-title">
      <Container>
        <SectionHeading
          id="principles-title"
          eyebrow={dict.principles.eyebrow}
          title={dict.principles.title}
          lead={dict.principles.lead}
        />
        <ol className="principle-grid" data-reveal-group>
          {pillars.map((pillar, index) => (
            <li key={pillar.heading} className="principle" data-reveal>
              <span className="principle__index" aria-hidden="true">{principleIndex(index, locale)}</span>
              <h3 lang="en" dir="ltr">{pillar.heading}</h3>
              <p>{pillar.text}</p>
            </li>
          ))}
        </ol>
      </Container>
    </section>
  )
}

export function Services({ services, locale = 'fa' }: { services: HomeContent['services']; locale?: Locale }) {
  const dict = getDictionary(locale)
  const available = services.filter((service) => !service.comingSoon)
  return (
    <section className="section section--muted" id="services" aria-labelledby="services-title">
      <Container>
        <SectionHeading
          id="services-title"
          eyebrow={dict.servicesSection.eyebrow}
          title={dict.servicesSection.title}
          lead={dict.servicesSection.lead}
        />
        <ul className="card-grid" data-reveal-group>
          {available.map((service) => {
            const image = serviceImage(service.slug)
            return (
              <li key={service.slug} data-reveal>
                <Link className="card card--media" href={localeHref(locale, `/services/${service.slug}`)}>
                  {image && (
                    <span className="card__media">
                      <Image
                        src={image.src}
                        alt=""
                        width={image.width}
                        height={image.height}
                        sizes="(max-width: 639px) 92vw, (max-width: 1023px) 46vw, 380px"
                        className="card__media-art"
                      />
                    </span>
                  )}
                  <span className="card__body">
                    <h3>{service.title}</h3>
                    <p>{service.summary}</p>
                    <span className="card__more">{dict.servicesSection.more} <span className="arrow" aria-hidden="true">←</span></span>
                  </span>
                </Link>
              </li>
            )
          })}
        </ul>
        <p className="grid-note">{dict.servicesSection.imageNote}</p>
        <div style={{ marginBlockStart: '1.75rem' }}>
          <Action href={localeHref(locale, '/services')} tone="glass">{dict.servicesSection.all}</Action>
        </div>
      </Container>
    </section>
  )
}

export function Founder({ founder, locale = 'fa' }: { founder: HomeContent['founder']; locale?: Locale }) {
  const dict = getDictionary(locale)
  const portraitAlt =
    locale === 'en'
      ? `Portrait of ${founder.name}, founder of Xennic`
      : FOUNDER_PORTRAIT.alt
  return (
    <section className="section" aria-labelledby="founder-title" data-testid="track-record-intro">
      <Container>
        <div className="glass glass--quiet founder" data-reveal>
          <div>
            <Eyebrow>{dict.founder.eyebrow}</Eyebrow>
            <h2 id="founder-title" className="h2">{founder.heading}</h2>
            {founder.summary && <p className="lede">{founder.summary}</p>}
            <p className="founder__text">{founder.text}</p>
            <p className="founder__note">{founder.note}</p>
            <Action href={localeHref(locale, '/track-record')} tone="glass">{dict.founder.readRecord}</Action>
          </div>
          <aside className="founder__aside" aria-label={dict.founder.asideLabel}>
            <div className="founder__portrait">
              <Image
                src={FOUNDER_PORTRAIT.src}
                alt={portraitAlt}
                width={FOUNDER_PORTRAIT.width}
                height={FOUNDER_PORTRAIT.height}
                sizes="(max-width: 900px) 60vw, 256px"
              />
            </div>
            <p className="founder__identity">
              <strong>{founder.name}</strong>
              <span>{founder.role} | Xennic</span>
            </p>
          </aside>
        </div>
      </Container>
    </section>
  )
}

export function Platform({ platform, locale = 'fa' }: { platform: HomeContent['platform']; locale?: Locale }) {
  const dict = getDictionary(locale)
  return (
    <section className="section section--muted" aria-labelledby="platform-title" data-testid="platform-intro">
      <Container>
        <div className="platform" data-reveal>
          <div className="platform__copy">
            <span className="badge">{platform.badge}</span>
            <h2 id="platform-title" className="h2" lang="en" dir="ltr">{platform.title}</h2>
            <p className="lede">{platform.description}</p>
            <p className="platform__status">{dict.platform.status}</p>
          </div>
          <div className="platform__art" aria-hidden="true">
            <Image src="/images/platform-glass.jpg" alt="" fill sizes="(max-width: 860px) 100vw, 46vw" style={{ objectFit: 'cover' }} />
          </div>
        </div>
      </Container>
    </section>
  )
}

export function ContactBand({ contact }: { contact: HomeContent['contact'] }) {
  return (
    <section className="section" aria-labelledby="contact-title">
      <Container>
        <div className="contact-band" data-reveal>
          <div>
            <h2 id="contact-title" className="h2">{contact.title}</h2>
            <p>{contact.text}</p>
          </div>
          <div className="contact-band__actions">
            <Action href={contact.primary.href}>{contact.primary.label}</Action>
            <Action href={contact.secondary.href} tone="glass">{contact.secondary.label}</Action>
          </div>
        </div>
      </Container>
    </section>
  )
}
