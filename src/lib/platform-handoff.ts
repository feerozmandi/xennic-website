/**
 * The hand-off from a calculator to the contact form.
 *
 * The Declare program publishes what it computed; this module turns those
 * numbers into the two lines a person reads in a request — a subject and a
 * message — and nothing else. It is deliberately pure: the numbers are the
 * program's, the words around them are the dictionary's, and the two meet
 * here so neither has to know about the other.
 */

/** What the program posts when the reader asks for a review. */
export type PlatformRequest = {
  tab?: string
  bankKvar?: number
  kwp?: number
  annualMwh?: number
  score?: number
}

/** The words the dictionary supplies for this one message. */
export type HandoffLabels = {
  subject: string
  intro: string
  bank: string
  plant: string
  triage: string
  score: string
  empty: string
}

/** Persian digits, so a number in a Persian sentence reads as one. */
export function toPersianDigits(value: string): string {
  return value.replace(/[0-9]/g, (digit) => '۰۱۲۳۴۵۶۷۸۹'[Number(digit)])
}

/** One decimal place, without a trailing `.0`. */
export function trim(value: number): string {
  return String(Math.round(value * 10) / 10)
}

/**
 * The body of the request.
 *
 * Only the panel the reader was actually working in is described: the other
 * two numbers would be stale defaults, and a request full of figures the
 * reader never touched is a request nobody trusts.
 */
export function requestSummary(
  request: PlatformRequest,
  labels: HandoffLabels,
  locale: 'fa' | 'en' = 'fa',
): string {
  // A Persian sentence carries Persian digits; an English one does not.
  const digits = locale === 'fa' ? toPersianDigits : (value: string) => value
  const perYear = locale === 'fa' ? ' MWh در سال' : ' MWh a year'

  const lines: string[] = []

  if (request.tab === 'pfc' && typeof request.bankKvar === 'number') {
    lines.push(`${labels.bank}: ${digits(trim(request.bankKvar))} kVAr`)
  }
  if (request.tab === 'solar' && typeof request.kwp === 'number') {
    const plant = `${labels.plant}: ${digits(String(Math.round(request.kwp)))} kWp`
    const annual =
      typeof request.annualMwh === 'number' ? ` — ${digits(trim(request.annualMwh))}${perYear}` : ''
    lines.push(plant + annual)
  }
  if (request.tab === 'audit' && typeof request.score === 'number') {
    // A score of zero means nothing was ticked, not that the site is in order.
    lines.push(
      request.score > 0
        ? `${labels.triage}: ${labels.score} ${digits(String(request.score))}`
        : `${labels.triage}: ${labels.empty}`,
    )
  }

  if (lines.length === 0) return labels.intro

  return [labels.intro, ...lines.map((line) => `• ${line}`)].join('\n')
}

/** The contact page a request goes to, with the message carried in the URL. */
export function contactHref(locale: 'fa' | 'en', subject: string, message: string): string {
  const base = locale === 'en' ? '/en/contact' : '/contact'
  const query = new URLSearchParams({ subject, message })
  return `${base}?${query.toString()}`
}
