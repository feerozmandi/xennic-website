import Image from 'next/image'
import Link from 'next/link'
import { Action, Container, Eyebrow, SectionHeading } from '../ui/primitives'
import { faNumber, type HomeContent } from '../../lib/home-content'

const principleIndex = (index: number) => faNumber(index + 1).padStart(2, '۰')

export function Hero({ content }: { content: HomeContent['hero'] }) {
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero__backdrop" aria-hidden="true">
        <Image
          src="/images/hero-energy.jpg"
          alt=""
          fill
          priority
          sizes="100vw"
          style={{ objectFit: 'cover' }}
        />
        <div className="hero__veil" />
      </div>
      <Container>
        <div className="hero__inner">
          <div className="hero__copy">
            <Eyebrow>{content.eyebrow}</Eyebrow>
            <h1 id="hero-title">{content.title}</h1>
            <p className="hero__summary">{content.summary}</p>
            <div className="hero__actions">
              <Action href={content.primary.href}>{content.primary.label}</Action>
              <Action href={content.secondary.href} tone="glass">{content.secondary.label}</Action>
            </div>
            <p className="hero__note">
              اطلاعات تماس رسمی فقط پس از تأیید سازمان منتشر می‌شود؛ تا آن زمان درخواست‌ها از صفحهٔ تماس پیگیری می‌شوند.
            </p>
          </div>
          <dl className="hero__facts glass glass--light">
            {content.facts.map((fact) => (
              <div key={fact.label}>
                <dt>{fact.label}</dt>
                <dd>{fact.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Container>
    </section>
  )
}

export function Principles({ pillars }: { pillars: HomeContent['pillars'] }) {
  return (
    <section className="section" aria-labelledby="principles-title">
      <Container>
        <SectionHeading
          id="principles-title"
          eyebrow="اصول کاری"
          title="چرا Xennic"
          lead="پنج اصلی که چارچوب تصمیم‌گیری مهندسی ما را شکل می‌دهند."
        />
        <ol className="principle-grid">
          {pillars.map((pillar, index) => (
            <li key={pillar.heading} className="principle">
              <span className="principle__index" aria-hidden="true">{principleIndex(index)}</span>
              <h3 lang="en" dir="ltr">{pillar.heading}</h3>
              <p>{pillar.text}</p>
            </li>
          ))}
        </ol>
      </Container>
    </section>
  )
}

export function Services({ services }: { services: HomeContent['services'] }) {
  const available = services.filter((service) => !service.comingSoon)
  return (
    <section className="section section--muted" id="services" aria-labelledby="services-title">
      <Container>
        <SectionHeading
          id="services-title"
          eyebrow="خدمات"
          title="از مشاورهٔ فنی تا نظارت و آموزش"
          lead="خدمات در حوزهٔ برق قدرت، تأسیسات، انرژی و آموزش تخصصی؛ هر خدمت با دامنهٔ مشخص و خروجی قابل استناد."
        />
        <ul className="card-grid">
          {available.map((service) => (
            <li key={service.slug}>
              <Link className="card" href={`/services/${service.slug}`}>
                <h3>{service.title}</h3>
                <p>{service.summary}</p>
                <span className="card__more">جزئیات خدمت <span aria-hidden="true">←</span></span>
              </Link>
            </li>
          ))}
        </ul>
        <div style={{ marginBlockStart: '1.75rem' }}>
          <Action href="/services" tone="glass">همهٔ خدمات و دوره‌ها</Action>
        </div>
      </Container>
    </section>
  )
}

export function Founder({ founder }: { founder: HomeContent['founder'] }) {
  return (
    <section className="section" aria-labelledby="founder-title" data-testid="track-record-intro">
      <Container>
        <div className="glass glass--quiet founder">
          <div>
            <Eyebrow>پیشینهٔ مؤسس</Eyebrow>
            <h2 id="founder-title" className="h2">{founder.heading}</h2>
            {founder.summary && <p className="lede">{founder.summary}</p>}
            <p className="founder__text">{founder.text}</p>
            <p className="founder__note">{founder.note}</p>
            <Action href="/track-record" tone="glass">مطالعهٔ پیشینهٔ حرفه‌ای</Action>
          </div>
          <aside className="founder__aside" aria-label="مشخصات مؤسس">
            <div className="founder__portrait" role="img" aria-label={`جای رزرو عکس رسمی ${founder.name}`}>
              <span>عکس رسمی مؤسس</span>
              <small>پس از دریافت فایل تأییدشده منتشر می‌شود</small>
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

export function Platform({ platform }: { platform: HomeContent['platform'] }) {
  return (
    <section className="section section--muted" aria-labelledby="platform-title" data-testid="platform-intro">
      <Container>
        <div className="platform">
          <div className="platform__copy">
            <span className="badge">{platform.badge}</span>
            <h2 id="platform-title" className="h2" lang="en" dir="ltr">{platform.title}</h2>
            <p className="lede">{platform.description}</p>
            <p className="platform__status">
              این بخش پیش‌نمایش طراحی است؛ هیچ قابلیت یا دسترسی جدیدی در سایت فعال نشده است.
            </p>
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
        <div className="contact-band">
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
