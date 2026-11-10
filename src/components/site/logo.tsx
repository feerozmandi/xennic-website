import Link from 'next/link'

/**
 * Text wordmark used until the official logo file is supplied by the owner.
 * Replace `Mark` with the approved artwork; do not redraw the trademark.
 */
export function Logo({ size = 'md' }: { size?: 'sm' | 'md' }) {
  return (
    <Link href="/" className="brand">
      <span className="brand__mark" aria-hidden="true" style={size === 'sm' ? { inlineSize: '2rem', blockSize: '2rem', fontSize: '.9rem' } : undefined}>X</span>
      <span>
        Xennic
        <span className="brand__sub">زر نور نیرو یکتا</span>
      </span>
    </Link>
  )
}
