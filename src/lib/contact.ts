/**
 * Owner-confirmed public contact details.
 *
 * Source: the owner supplied every value in a single message on 2026-11-10
 * (phone, two mailboxes, Bale, Telegram, Instagram). Values are copied
 * verbatim; nothing here may be inferred, completed or "improved" by guesswork.
 * A new channel needs a new explicit owner confirmation, and — where the Vault
 * covers it — a matching approved-copy entry first.
 *
 * The Instagram URL is the only derived value: a bare handle (`@xennic.ir`)
 * is rendered as the canonical profile address for that same handle.
 */
import { FOUNDER_BIO } from './approved-copy'
import { FOUNDER_NAME } from './home-content'

export type ContactMethod = {
  id: string
  label: string
  /** Human-readable value exactly as shown on the page. */
  value: string
  href: string
  /** Opens outside the site; rendered with rel="noopener noreferrer". */
  external: boolean
  hint?: string
}

export const PHONE_DISPLAY = '۰۹۱۲۴۵۳۳۸۷۸'
export const PHONE_HREF = 'tel:+989124533878'

export const PHONE_METHOD: ContactMethod = {
  id: 'phone',
  label: 'تلفن همراه',
  value: PHONE_DISPLAY,
  href: PHONE_HREF,
  external: false,
  hint: 'تماس مستقیم با مؤسس',
}

export const EMAIL_METHODS: ContactMethod[] = [
  {
    id: 'email-info',
    label: 'رایانامهٔ رسمی',
    value: 'info@xennic.ir',
    href: 'mailto:info@xennic.ir',
    external: false,
  },
  {
    id: 'email-founder',
    label: 'رایانامهٔ مؤسس',
    value: 'feerozmandiha@gmail.com',
    href: 'mailto:feerozmandiha@gmail.com',
    external: false,
  },
]

export const SOCIAL_METHODS: ContactMethod[] = [
  { id: 'bale', label: 'بله', value: 'ble.ir/xennic', href: 'https://ble.ir/xennic', external: true },
  { id: 'telegram', label: 'تلگرام', value: 't.me/xennicco', href: 'https://t.me/xennicco', external: true },
  {
    id: 'instagram',
    label: 'اینستاگرام',
    value: '@xennic.ir',
    href: 'https://instagram.com/xennic.ir',
    external: true,
  },
]

export const CONTACT_METHODS: ContactMethod[] = [PHONE_METHOD, ...EMAIL_METHODS, ...SOCIAL_METHODS]

/**
 * Real portrait of the founder, provided by the owner on 2026-11-10.
 * The supplied file is 288×288; it is never upscaled, so the layout keeps the
 * rendered size at or below that.
 */
export const FOUNDER_PORTRAIT = {
  src: '/images/founder.jpg',
  width: 288,
  height: 288,
  alt: `پرترهٔ ${FOUNDER_NAME}، مؤسس Xennic`,
} as const

/** Verbatim leading clause of the approved biography; no new claim is added. */
export const FOUNDER_HEADLINE = FOUNDER_BIO.split('؛')[0].split('—').slice(1).join('—').trim()
