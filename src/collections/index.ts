import type { Access, CollectionConfig } from 'payload'

const staffOnly: Access = ({ req: { user } }) => Boolean(user)
const access = { create: staffOnly, read: staffOnly, update: staffOnly, delete: staffOnly }

export const Staff: CollectionConfig = {
  slug: 'staff',
  auth: true,
  admin: { useAsTitle: 'email' },
  access,
  fields: [{ name: 'name', type: 'text', required: true }],
}

export const Pages: CollectionConfig = {
  slug: 'pages', access, admin: { useAsTitle: 'title' },
  fields: [
    { name: 'title', type: 'text', required: true },
    { name: 'slug', type: 'text', required: true, unique: true },
    { name: 'content', type: 'richText' },
  ],
}

export const Services: CollectionConfig = {
  slug: 'services', access, admin: { useAsTitle: 'title' },
  fields: [
    { name: 'title', type: 'text', required: true },
    { name: 'slug', type: 'text', required: true, unique: true },
    { name: 'summary', type: 'textarea' },
    { name: 'content', type: 'richText' },
  ],
}

export const TrackRecordItems: CollectionConfig = {
  slug: 'track-record-items', access, admin: { useAsTitle: 'title' },
  fields: [
    { name: 'title', type: 'text', required: true },
    { name: 'role', type: 'text' },
    { name: 'description', type: 'textarea' },
  ],
}

export const TeamMembers: CollectionConfig = {
  slug: 'team-members', access, admin: { useAsTitle: 'name' },
  fields: [
    { name: 'name', type: 'text', required: true },
    { name: 'role', type: 'text' },
    { name: 'biography', type: 'textarea' },
  ],
}

export const FAQs: CollectionConfig = {
  slug: 'faqs', access, admin: { useAsTitle: 'question' },
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
  slug: 'media', access, upload: true,
  fields: [{ name: 'alt', type: 'text', required: true }],
}
