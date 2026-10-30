# Xennic website

Initial local-development scaffold for the Persian corporate website and the future Xennic modular monolith. The source of truth for architecture and decisions is the [Xennic Vault: META-INT-150](https://github.com/feerozmandi/ZNNY-Xennic-Vault/blob/dev/00_Meta/Integration/META-INT-150%20%E2%80%94%20%DB%8C%DA%A9%D9%BE%D8%A7%D8%B1%DA%86%D9%87%E2%80%8C%D8%B3%D8%A7%D8%B2%DB%8C%20%D9%85%D8%B9%D9%85%D8%A7%D8%B1%DB%8C%20%D9%88%D8%A8%E2%80%8C%D8%B3%D8%A7%DB%8C%D8%AA%20%D9%88%20%D9%BE%D9%84%D8%AA%D9%81%D8%B1%D9%85%20Xennic.md); see also L2-MKT-002 through L2-MKT-005 in that Vault.

This is a **development scaffold**, not a production release. Approved L2-MKT-004 content is seeded for the home, about, services, founder and track-record pages; other pages remain placeholders. Forms, Umami, automation integrations and production deployment are not implemented yet. There is no public customer login or registration.

## Project progress

Persian management reports, current status and update guidance are available in [`docs/README.md`](docs/README.md).

## Fonts

IRANSans is the approved font, but the site uses the system font until an organizational license is purchased from `fontiran.com`. Licensed font files must never be committed to this public repository; keep them outside Git. The ignore rules are a safeguard, not a guarantee against forced additions.

## Local setup

Requirements: Node.js 20.18.1 or newer, npm and Docker Compose. PostgreSQL 16 runs in a local development container only.

1. Copy `.env.example` to `.env`. Set `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL`, and a long random `PAYLOAD_SECRET` locally. Never commit or share these values. The PostgreSQL values and `DATABASE_URL` must refer to the same local database; URL-encode special characters in the URL. The database port is bound to `127.0.0.1` on the development machine.
2. Install and start the database:

   ```sh
   npm ci
   docker compose up -d
   npm run db:init
   npm run seed
   npm run dev
   ```

3. Open `http://localhost:3000` and `/admin`. On a fresh local database, create the first staff account through Payload's setup screen. Do not expose an uninitialized admin to the public. The approved public content collections are readable without login; writes and access to staff and leads are restricted to staff. Seed only inserts missing records and never overwrites existing CMS edits. After updating an existing development database, re-run `npm run seed` to add newly introduced records such as `track-record-intro`; if a record with that slug already exists, review and edit it in the CMS instead of expecting seed to replace it.

`npm run db:init` is an idempotent development initialization script: it creates the `website` schema and the separate `shared.customers` table. On databases created by the earlier scaffold, it removes the obsolete `organization_name` column only if it contains no data; otherwise it stops without changing the table so the data can be reviewed before migration. Payload's development schema push creates its own tables in `website`. The Payload PostgreSQL `schemaName` option is experimental; keep table names distinct across schemas and validate future schema changes carefully. Neither this script nor development schema push is a production migration strategy. Future modules and schemas are intentionally not implemented.

## Checks

```sh
npm run typecheck
npm run lint
npm run test:compat
npm run build
# With the development server and database running:
npm run test:smoke
```

Payload types and import map can be regenerated using `npm run generate:types` and `npm run generate:importmap` with a configured `.env`.

## Initial data model

- `Staff`: name plus Payload authentication fields.
- `Page`: title, slug, content.
- `Service`: title, slug, summary, content.
- `TrackRecordItem`: title, role, description; not company projects.
- `TeamMember`: name, role, biography.
- `FAQ`: question, answer.
- `LeadSubmission`: name, organization, phone, email, subject, message, source, assigned staff, status, plus Payload timestamps. Public form submission is not enabled.
- `Media`: file and alt text.
- `shared.customers`: UUID, name (person or organization), email, phone, source and creation time. This is independent of staff and is not a Payload auth collection.

Fields are intentionally minimal and were approved by the owner; form validation and handling still require implementation and review. No Article, TechnicalNote or CaseStudy collections are included at this stage. Actual customer/lead handling, validations, retention and permissions require further design before public use.

## Security and deployment status

The lockfile has outstanding upstream `npm audit` findings; review and resolve them before exposing the application or CMS publicly. The `graphql-scalars` and `happy-dom` security overrides use versions outside their upstream parents’ declared ranges; compatibility checks reduce risk but do not establish official support. Reassess the overrides when upstream packages provide supported fixes. The scaffold is not deployed to the company's VPS. Deployment and integration with automation remain dependent on infrastructure readiness and separate approval.
