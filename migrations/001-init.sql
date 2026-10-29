-- The customer identity is shared across domains, not a Payload Staff account.
CREATE SCHEMA IF NOT EXISTS website;
CREATE SCHEMA IF NOT EXISTS shared;
CREATE TABLE IF NOT EXISTS shared.customers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text,
  email text,
  phone text,
  source text,
  created_at timestamptz NOT NULL DEFAULT now()
);
