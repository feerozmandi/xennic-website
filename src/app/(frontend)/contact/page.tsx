import type { Metadata } from 'next'
import Image from 'next/image'
import Link from 'next/link'
import { ContactForm } from '@/components/contact/contact-form'
import { Container, Eyebrow } from '@/components/ui/primitives'
import { FOUNDER_NAME } from '@/lib/home-content'
import { CONTACT_METHODS, EMAIL_METHODS, FOUNDER_HEADLINE, FOUNDER_PORTRAIT, PHONE_METHOD, SOCIAL_METHODS } from '@/lib/contact'
import { pageMetadata } from '@/lib/seo'

export const metadata: Metadata = pageMetadata({
  title: 'تماس با ما',
  description:
    'مسیرهای تماس رسمی Xennic: تلفن، رایانامه، بله، تلگرام و اینستاگرام، همراه با فرم درخواست تماس.',
  path: '/contact',
})

function MethodLink({ method }: { method: (typeof CONTACT_METHODS)[number] }) {
  return (
    <li className="contact-method">
      <span className="contact-method__label">{method.label}</span>
      <a
        className="contact-method__value"
        href={method.href}
        dir="ltr"
        {...(method.external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
      >
        {method.value}
        {method.external && (
          <span aria-hidden="true" className="contact-method__mark">
            ↗
          </span>
        )}
        {method.external && <span className="sr-only"> (در پنجرهٔ تازه باز می‌شود)</span>}
      </a>
      {method.hint && <span className="contact-method__hint">{method.hint}</span>}
    </li>
  )
}

export default function ContactPage() {
  return (
    <Container>
      <div className="page">
        <nav aria-label="مسیر صفحه" className="breadcrumb">
          <Link href="/">خانه</Link>
          <span aria-hidden="true"> / </span>
          <span>تماس با ما</span>
        </nav>

        <header className="contact-head">
          <Eyebrow>مسیرهای تماس</Eyebrow>
          <h1 className="h1">تماس با Xennic</h1>
          <p className="lede">
            برای گفت‌وگو دربارهٔ پروژه، درخواست مشاورهٔ فنی یا پیگیری یک موضوع، از هر یک از مسیرهای زیر استفاده
            کنید. همین اطلاعات در پایین همهٔ صفحه‌ها هم آمده است.
          </p>
        </header>

        <div className="contact-layout">
          <div className="contact-side">
            <section className="panel" aria-labelledby="contact-direct-title">
              <h2 id="contact-direct-title" className="h3">تماس مستقیم</h2>
              <ul className="contact-methods">
                <MethodLink method={PHONE_METHOD} />
                {EMAIL_METHODS.map((method) => (
                  <MethodLink key={method.id} method={method} />
                ))}
              </ul>
            </section>

            <section className="panel" aria-labelledby="contact-social-title">
              <h2 id="contact-social-title" className="h3">پیام‌رسان‌ها و شبکه‌های اجتماعی</h2>
              <ul className="contact-methods">
                {SOCIAL_METHODS.map((method) => (
                  <MethodLink key={method.id} method={method} />
                ))}
              </ul>
            </section>

            <section className="panel founder-card" aria-labelledby="contact-founder-title">
              <h2 id="contact-founder-title" className="h3">دربارهٔ مؤسس</h2>
              <div className="founder-card__body">
                <Image
                  src={FOUNDER_PORTRAIT.src}
                  alt={FOUNDER_PORTRAIT.alt}
                  width={FOUNDER_PORTRAIT.width}
                  height={FOUNDER_PORTRAIT.height}
                  sizes="144px"
                  className="founder-card__photo"
                />
                <div>
                  <p className="founder-card__name">{FOUNDER_NAME}</p>
                  <p className="founder-card__role">مؤسس | Xennic</p>
                  <p className="founder-card__bio">{FOUNDER_HEADLINE}</p>
                </div>
              </div>
              <Link className="text-link" href="/track-record">
                مطالعهٔ پیشینهٔ حرفه‌ای
              </Link>
            </section>
          </div>

          <section className="panel panel--form" aria-labelledby="contact-form-title">
            <ContactForm />
          </section>
        </div>
      </div>
    </Container>
  )
}
