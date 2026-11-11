/**
 * Line icons for the footer.
 *
 * Hand-drawn SVG rather than a dependency: the site needs six glyphs, and a
 * package would add weight to every page for them. Every icon is decorative
 * (`aria-hidden`); the text beside it — or the link's own accessible name —
 * carries the meaning, so an icon is never the only label of an action.
 *
 * Shapes are generic metaphors (handset, envelope, at-sign, chat bubble, paper
 * plane, camera), not redrawn brand marks: the official artwork is only ever
 * placed as the approved file from the Vault.
 */
type IconProps = { className?: string }

const base = {
  width: 20,
  height: 20,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.7,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
  focusable: false,
}

export function PhoneIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M6.5 3.5h-1A2.5 2.5 0 0 0 3 6.2c.3 6.9 5.9 12.5 12.8 12.8a2.5 2.5 0 0 0 2.7-2.5v-1a1.6 1.6 0 0 0-1.2-1.6l-2.4-.6a1.6 1.6 0 0 0-1.6.5l-.8.9a12.6 12.6 0 0 1-5.2-5.2l.9-.8a1.6 1.6 0 0 0 .5-1.6l-.6-2.4A1.6 1.6 0 0 0 6.5 3.5Z" />
    </svg>
  )
}

export function MailIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <rect x="3" y="5" width="18" height="14" rx="2.5" />
      <path d="m3.6 7.2 7.2 5.1a2 2 0 0 0 2.4 0l7.2-5.1" />
    </svg>
  )
}

export function AtIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <circle cx="12" cy="12" r="3.6" />
      <path d="M15.6 8.4v4.6a2.6 2.6 0 0 0 5.2 0V12a8.8 8.8 0 1 0-3.6 7.1" />
    </svg>
  )
}

export function ChatIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M20.5 11.6a7.7 7.7 0 0 1-8.3 7.7 9 9 0 0 1-2.5-.4L4.5 20.5l1.4-4.2a7.4 7.4 0 0 1-1.3-4.3 7.7 7.7 0 0 1 8-7.5 7.7 7.7 0 0 1 7.9 7.1Z" />
      <path d="M9.2 11.7h.01M12.5 11.7h.01M15.8 11.7h.01" strokeWidth="2.2" />
    </svg>
  )
}

export function PlaneIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M20.6 3.9 3.8 10.4a.6.6 0 0 0 0 1.1l6.3 2.3 2.3 6.3a.6.6 0 0 0 1.1 0Z" />
      <path d="m10.1 13.8 4.4-4.4" />
    </svg>
  )
}

export function CameraIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <rect x="3" y="3.5" width="18" height="18" rx="5" />
      <circle cx="12" cy="12.5" r="4" />
      <path d="M17.2 7.3h.01" strokeWidth="2.2" />
    </svg>
  )
}

/** Map of the confirmed contact ids to their glyph. */
export const CONTACT_ICONS = {
  phone: PhoneIcon,
  'email-info': MailIcon,
  'email-founder': AtIcon,
  bale: ChatIcon,
  telegram: PlaneIcon,
  instagram: CameraIcon,
} as const
