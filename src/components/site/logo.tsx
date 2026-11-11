import Image from 'next/image'
import Link from 'next/link'
import { getDictionary, localeHref, type Locale } from '@/lib/i18n'

/**
 * Official brand lockup.
 *
 * Assets come from the approved artwork in the Vault (`02_PreLaunch/L1-BRD/attachments`)
 * and are used unmodified apart from trimming the transparent margin. Two
 * variants exist because the wordmark is mint on dark and teal on light: the
 * stylesheet shows whichever one matches the active theme.
 *
 * The artwork is a trademark: never redraw it, recolour it or rebuild it from
 * type. Re-export from the master SVG if the source ever changes.
 */
const LOGO = { width: 292, height: 139 }

export function Logo({ size = 'md', locale = 'fa' }: { size?: 'sm' | 'md' | 'lg'; locale?: Locale }) {
  const dict = getDictionary(locale)
  return (
    <Link href={localeHref(locale, '/')} className={`brand brand--${size}`} aria-label={dict.logoHome}>
      <span className="brand__mark">
        <Image
          src="/brand/xennic-logo-on-dark.webp"
          alt=""
          width={LOGO.width}
          height={LOGO.height}
          priority={size !== 'lg'}
          className="brand__art brand__art--on-dark"
        />
        <Image
          src="/brand/xennic-logo-on-light.webp"
          alt=""
          width={LOGO.width}
          height={LOGO.height}
          priority={size !== 'lg'}
          className="brand__art brand__art--on-light"
        />
      </span>
      <span className="brand__text" aria-hidden="true">
        <span className="brand__sub">{dict.brandSub}</span>
      </span>
    </Link>
  )
}
