import { withPayload } from '@payloadcms/next/withPayload'
import type { NextConfig } from 'next'

const config: NextConfig = {
  // The Arena live preview uses a proxied host rather than localhost.
  allowedDevOrigins: ['*.e2b.app'],
  // This image is built for preview; indexing directives are not access control.
  // Private surfaces are excluded from indexing in production as well, as a
  // second line of defence behind `robots.ts` and the per-page metadata.
  async headers() {
    if (process.env.XENNIC_PREVIEW === '1') {
      return [{ source: '/:path*', headers: [{ key: 'X-Robots-Tag', value: 'noindex, nofollow' }] }]
    }
    return [
      { source: '/admin', headers: [{ key: 'X-Robots-Tag', value: 'noindex, nofollow' }] },
      { source: '/admin/:path*', headers: [{ key: 'X-Robots-Tag', value: 'noindex, nofollow' }] },
      { source: '/api/:path*', headers: [{ key: 'X-Robots-Tag', value: 'noindex, nofollow' }] },
      { source: '/health', headers: [{ key: 'X-Robots-Tag', value: 'noindex, nofollow' }] },
    ]
  },
}

export default withPayload(config)
