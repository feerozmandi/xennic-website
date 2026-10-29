import { withPayload } from '@payloadcms/next/withPayload'
import type { NextConfig } from 'next'

const config: NextConfig = {
  // The Arena live preview uses a proxied host rather than localhost.
  allowedDevOrigins: ['*.e2b.app'],
}

export default withPayload(config)
