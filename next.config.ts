import { withPayload } from '@payloadcms/next/withPayload'
import type { NextConfig } from 'next'

const config: NextConfig = {
  // The Arena live preview uses a proxied host rather than localhost.
  allowedDevOrigins: ['*.e2b.app'],
  // This image is built for preview; indexing directives are not access control.
  async headers() {
    return process.env.XENNIC_PREVIEW === '1'
      ? [{ source: '/:path*', headers: [{ key: 'X-Robots-Tag', value: 'noindex, nofollow' }] }]
      : []
  },
}

export default withPayload(config)
