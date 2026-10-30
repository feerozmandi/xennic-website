import { postgresAdapter } from '@payloadcms/db-postgres'
import { lexicalEditor } from '@payloadcms/richtext-lexical'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { buildConfig } from 'payload'
import sharp from 'sharp'
import { FAQs, LeadSubmissions, Media, Pages, Services, Staff, TeamMembers, TrackRecordItems } from './collections'

const dirname = path.dirname(fileURLToPath(import.meta.url))

export default buildConfig({
  admin: { user: Staff.slug, importMap: { baseDir: dirname } },
  collections: [Staff, Pages, Services, TrackRecordItems, TeamMembers, FAQs, LeadSubmissions, Media],
  db: postgresAdapter({ pool: { connectionString: process.env.DATABASE_URL }, schemaName: 'website', disableCreateDatabase: true }),
  // Preview must not emit password reset links or other emails to console or a real provider.
  ...(process.env.XENNIC_PREVIEW === '1' ? { email: () => ({
    name: 'preview-disabled', defaultFromAddress: 'disabled@example.invalid', defaultFromName: 'Preview',
    sendEmail: async () => { throw new Error('Email is disabled in preview.') },
  }) } : {}),
  editor: lexicalEditor(),
  secret: process.env.PAYLOAD_SECRET || '',
  sharp,
  typescript: { outputFile: path.resolve(dirname, 'payload-types.ts') },
})
