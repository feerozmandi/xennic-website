import Link from 'next/link'
import type { ReactNode } from 'react'
import { getDictionary, localeHref, type Locale } from '@/lib/i18n'
import { clientScript } from '@/lib/client-script'
import { themeScript } from '@/lib/theme-script'
import { RevealController } from './ui/reveal'
import { SiteFooter } from './site/footer'
import { SiteHeader } from './site/header'
import { Container } from './ui/primitives'

/**
 * The document of one language edition: `<html lang>` and `dir` are decided here,
 * so every route in the tree carries the right language for assistive technology,
 * the browser and search engines.
 */
export function SiteDocument({ locale = 'fa', children }: { locale?: Locale; children: ReactNode }) {
  const dict = getDictionary(locale)
  return (
    <html lang={dict.htmlLang} dir={dict.dir} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <script dangerouslySetInnerHTML={{ __html: clientScript }} />
      </head>
      <body>
        <SiteShell locale={locale}>{children}</SiteShell>
      </body>
    </html>
  )
}

/**
 * Header, main and footer for one language edition.
 *
 * The locale is passed explicitly instead of being read from context: the two
 * editions are separate route trees with their own `<html lang>` and `dir`, so
 * every shell render knows — and states — which language it is drawing.
 */
export function SiteShell({ locale = 'fa', children }: { locale?: Locale; children: ReactNode }) {
  const dict = getDictionary(locale)
  return (
    <>
      <RevealController />
      <a href="#main-content" className="skip-link">{dict.skipToContent}</a>
      <SiteHeader locale={locale} />
      <main id="main-content">{children}</main>
      <SiteFooter locale={locale} />
    </>
  )
}

export function PlaceholderPage({ title, locale = 'fa', children }: { title: string; locale?: Locale; children?: ReactNode }) {
  const dict = getDictionary(locale)
  return (
    <Container>
      <div className="page">
        <nav aria-label={dict.breadcrumb} className="breadcrumb">
          <Link href={localeHref(locale, '/')}>{dict.home}</Link>
          <span aria-hidden="true"> / </span>
          <span>{title}</span>
        </nav>
        <h1>{title}</h1>
        <p className="placeholder">{dict.placeholderBody}</p>
        {children}
      </div>
    </Container>
  )
}
