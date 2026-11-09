// Only a fixed HTTPS origin may be selected; never trust the request host.
export const APPROVED_PREVIEW_ORIGIN = 'https://preview.xennic.ir'
export const APPROVED_APEX_ORIGIN = 'https://xennic.ir'
const APPROVED_ORIGINS = [APPROVED_PREVIEW_ORIGIN, APPROVED_APEX_ORIGIN]

export function previewOrigin(env: NodeJS.ProcessEnv): string | undefined {
  if (env.XENNIC_PREVIEW !== '1') return undefined
  if (!env.PREVIEW_ORIGIN || !APPROVED_ORIGINS.includes(env.PREVIEW_ORIGIN)) {
    throw new Error('PREVIEW_ORIGIN must be an approved exact HTTPS origin.')
  }
  return env.PREVIEW_ORIGIN
}

// Cookie extraction cannot protect unauthenticated login. Allow headerless
// non-browser clients; browsers supplying an untrusted Origin or cross-site
// fetch metadata cannot create a Staff session in preview.
export function previewLoginAllowed(headers: Headers, expectedOrigin = APPROVED_PREVIEW_ORIGIN): boolean {
  if (!APPROVED_ORIGINS.includes(expectedOrigin)) return false
  const origin = headers.get('origin')
  if (origin !== null) return origin === expectedOrigin
  return headers.get('sec-fetch-site') !== 'cross-site'
}
