import { APIError, type Access, type CollectionConfig } from 'payload'
import { previewLoginAllowed } from '../lib/preview-security'

const staffOnly: Access = ({ req: { user } }) => Boolean(user)
const access = { create: staffOnly, read: staffOnly, update: staffOnly, delete: staffOnly }
const publicContentAccess = { ...access, read: () => true }

export const Staff: CollectionConfig = {
  slug: 'staff',
  // The preview HTTPS session is host-only, HttpOnly (Payload), and scoped to '/'.
  auth: process.env.XENNIC_PREVIEW === '1' ? { cookies: { secure: true, sameSite: 'Lax' } } : true,
  ...(process.env.XENNIC_PREVIEW === '1' ? { hooks: { beforeLogin: [({ req }) => {
    if (!previewLoginAllowed(req.headers)) throw new APIError('Untrusted login origin', 403)
  }] } } : {}),
  admin: { useAsTitle: 'email' },
  access,
  fields: [{ name: 'name', type: 'text', required: true }],
}

export const Pages: CollectionConfig = {
  slug: 'pages', access: publicContentAccess, admin: { useAsTitle: 'title' },
  fields: [
    { name: 'title', type: 'text', required: true },
    { name: 'slug', type: 'text', required: true, unique: true },
    { name: 'summary', type: 'textarea' },
    { name: 'content', type: 'richText' },
  ],
}

export const Services: CollectionConfig = {
  slug: 'services', access: publicContentAccess, admin: { useAsTitle: 'title' },
  fields: [
    { name: 'title', type: 'text', required: true },
    { name: 'slug', type: 'text', required: true, unique: true },
    { name: 'summary', type: 'textarea' },
    { name: 'content', type: 'richText' },
    { name: 'cta', type: 'text' },
    { name: 'comingSoon', type: 'checkbox', defaultValue: false },
  ],
}

export const TrackRecordItems: CollectionConfig = {
  slug: 'track-record-items', access: publicContentAccess, admin: { useAsTitle: 'title' },
  fields: [
    { name: 'title', type: 'text', required: true },
    { name: 'role', type: 'text' },
    { name: 'description', type: 'textarea' },
  ],
}

export const TeamMembers: CollectionConfig = {
  slug: 'team-members', access: publicContentAccess, admin: { useAsTitle: 'name' },
  fields: [
    { name: 'name', type: 'text', required: true },
    { name: 'role', type: 'text' },
    { name: 'biography', type: 'textarea' },
  ],
}

export const FAQs: CollectionConfig = {
  slug: 'faqs', access: publicContentAccess, admin: { useAsTitle: 'question' },
  fields: [
    { name: 'question', type: 'text', required: true },
    { name: 'answer', type: 'textarea', required: true },
  ],
}

export const LeadSubmissions: CollectionConfig = {
  slug: 'lead-submissions', access, admin: { useAsTitle: 'name' },
  fields: [
    { name: 'name', type: 'text', required: true },
    { name: 'organization', type: 'text' },
    { name: 'phone', type: 'text' },
    { name: 'email', type: 'email' },
    { name: 'subject', type: 'text' },
    { name: 'message', type: 'textarea' },
    { name: 'source', type: 'text' },
    { name: 'assignedStaff', type: 'relationship', relationTo: 'staff' },
    { name: 'status', type: 'select', required: true, defaultValue: 'new', options: ['new', 'in-review', 'closed'] },
  ],
}

export const Media: CollectionConfig = {
  slug: 'media', access: publicContentAccess, upload: { staticDir: process.env.MEDIA_DIR || 'media' },
  fields: [{ name: 'alt', type: 'text', required: true }],
}
