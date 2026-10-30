// Preview accepts exactly the owner-approved HTTPS origin; never use request headers.
export const APPROVED_PREVIEW_ORIGIN = 'https://preview.xennic.ir'

export function previewOrigin(env: NodeJS.ProcessEnv): string | undefined {
  if (env.XENNIC_PREVIEW !== '1') return undefined
  if (env.PREVIEW_ORIGIN !== APPROVED_PREVIEW_ORIGIN) {
    throw new Error('PREVIEW_ORIGIN must be exactly https://preview.xennic.ir in preview mode.')
  }
  return APPROVED_PREVIEW_ORIGIN
}

// Cookie extraction cannot protect unauthenticated login. Allow headerless
// non-browser clients; browsers supplying an untrusted Origin or cross-site
// fetch metadata cannot create a Staff session in preview.
export function previewLoginAllowed(headers: Headers): boolean {
  const origin = headers.get('origin')
  if (origin !== null) return origin === APPROVED_PREVIEW_ORIGIN
  return headers.get('sec-fetch-site') !== 'cross-site'
}
