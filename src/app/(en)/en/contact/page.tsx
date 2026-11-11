import type { Metadata } from 'next'
import Image from 'next/image'
import Link from 'next/link'
import { ContactForm } from '@/components/contact/contact-form'
import { Breadcrumb } from '@/components/content'
import { Container, Eyebrow } from '@/components/ui/primitives'
import { getDictionary, localeHref } from '@/lib/i18n'
import { en } from '@/lib/i18n-content'
import { EMAIL_METHODS, FOUNDER_PORTRAIT, phoneMethod, SOCIAL_METHODS } from '@/lib/contact'
import { pageMetadata } from '@/lib/seo'

export const metadata: Metadata = pageMetadata({
  title: 'Contact Xennic',
  description:
    'Official Xennic contact channels: phone, email, Bale, Telegram and Instagram, together with a contact request form.',
  path: '/en/contact',
  locale: 'en',
})

const dict = getDictionary('en')

const LABELS: Record<string, string> = {
  phone: dict.methods.phone,
  'email-info': dict.methods.emailInfo,
  'email-founder': dict.methods.emailFounder,
  bale: dict.methods.bale,
  telegram: dict.methods.telegram,
  instagram: dict.methods.instagram,
}

function MethodLink({ method }: { method: (typeof EMAIL_METHODS)[number] | (typeof SOCIAL_METHODS)[number] }) {
  return (
    <li className="contact-method">
      <span className="contact-method__label">{LABELS[method.id] ?? method.label}</span>
      <a
        className="contact-method__value"
        href={method.href}
        dir="ltr"
        {...(method.external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
      >
        {method.value}
        {method.external && (
          <span aria-hidden="true" className="contact-method__mark">↗</span>
        )}
        {method.external && <span className="sr-only"> ({dict.opensInNewTab})</span>}
      </a>
      {method.hint && <span className="contact-method__hint">{dict.methods.phoneHint}</span>}
    </li>
  )
}

export default function EnglishContactPage() {
  return (
    <Container>
      <div className="page">
        <Breadcrumb
          locale="en"
          trail={[{ href: localeHref('en', '/'), label: dict.home }, { label: dict.contactRoutes }]}
        />
        <header className="contact-head">
          <Eyebrow>{dict.contactPage.eyebrow}</Eyebrow>
          <h1 className="h1">{dict.contactPage.title}</h1>
          <p className="lede">{dict.contactPage.lead}</p>
        </header>

        <div className="contact-layout">
          <div className="contact-side">
            <section className="panel" aria-labelledby="contact-direct-title">
              <h2 id="contact-direct-title" className="h3">{dict.contactPage.direct}</h2>
              <ul className="contact-methods">
                <MethodLink method={phoneMethod('en')} />
                {EMAIL_METHODS.map((method) => (
                  <MethodLink key={method.id} method={method} />
                ))}
              </ul>
            </section>

            <section className="panel" aria-labelledby="contact-social-title">
              <h2 id="contact-social-title" className="h3">{dict.contactPage.social}</h2>
              <ul className="contact-methods">
                {SOCIAL_METHODS.map((method) => (
                  <MethodLink key={method.id} method={method} />
                ))}
              </ul>
            </section>

            <section className="panel founder-card" aria-labelledby="contact-founder-title">
              <h2 id="contact-founder-title" className="h3">{dict.contactPage.founder}</h2>
              <div className="founder-card__body">
                <Image
                  src={FOUNDER_PORTRAIT.src}
                  alt={`Portrait of ${en.founderNameLatin}, founder of Xennic`}
                  width={FOUNDER_PORTRAIT.width}
                  height={FOUNDER_PORTRAIT.height}
                  sizes="144px"
                  className="founder-card__photo"
                />
                <div>
                  <p className="founder-card__name">{en.founderNameLatin}</p>
                  <p className="founder-card__role">Founder | Xennic</p>
                  <p className="founder-card__bio">{en.founderHeadline}</p>
                </div>
              </div>
              <Link className="text-link" href={localeHref('en', '/track-record')}>
                {dict.contactPage.founderLink}
              </Link>
            </section>
          </div>

          <section className="panel panel--form" aria-labelledby="contact-form-title">
            <ContactForm locale="en" />
          </section>
        </div>
      </div>
    </Container>
  )
}
