-- The finalized model uses one name field for either a person or an organization.
-- Do not discard values written by an earlier scaffold.
DO $$
DECLARE
  has_organization_data boolean;
BEGIN
  LOCK TABLE shared.customers IN ACCESS EXCLUSIVE MODE;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'shared' AND table_name = 'customers'
      AND column_name = 'organization_name'
  ) THEN
    EXECUTE 'SELECT EXISTS (SELECT 1 FROM shared.customers WHERE organization_name IS NOT NULL)'
      INTO has_organization_data;
    IF has_organization_data THEN
      RAISE EXCEPTION 'shared.customers.organization_name contains data; review it before migrating';
    END IF;
    ALTER TABLE shared.customers DROP COLUMN organization_name;
  END IF;
END $$;
