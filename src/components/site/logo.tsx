import Image from 'next/image'
import Link from 'next/link'

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

export function Logo({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  return (
    <Link href="/" className={`brand brand--${size}`} aria-label="Xennic — زر نور نیرو یکتا، صفحهٔ اصلی">
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
        <span className="brand__sub">زر نور نیرو یکتا</span>
      </span>
    </Link>
  )
}
