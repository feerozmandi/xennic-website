import { MigrateUpArgs, sql } from '@payloadcms/db-postgres'

export async function up({ db }: MigrateUpArgs): Promise<void> {
  // Payload 3.91.0 ships two Drizzle copies with incompatible private types.
  // @ts-expect-error Generated SQL is runtime-compatible across those copies.
  await db.execute(sql`
   CREATE SCHEMA IF NOT EXISTS "website";
  CREATE SCHEMA IF NOT EXISTS "shared";
  CREATE TABLE "shared"."customers" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "name" text,
    "email" text,
    "phone" text,
    "source" text,
    "created_at" timestamptz NOT NULL DEFAULT now()
  );
  CREATE TYPE "website"."enum_lead_submissions_status" AS ENUM('new', 'in-review', 'closed');
  CREATE TABLE "website"."staff_sessions" (
    "_order" integer NOT NULL,
    "_parent_id" integer NOT NULL,
    "id" varchar PRIMARY KEY NOT NULL,
    "created_at" timestamp(3) with time zone,
    "expires_at" timestamp(3) with time zone NOT NULL
  );

  CREATE TABLE "website"."staff" (
    "id" serial PRIMARY KEY NOT NULL,
    "name" varchar NOT NULL,
    "updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
    "created_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
    "email" varchar NOT NULL,
    "reset_password_token" varchar,
    "reset_password_expiration" timestamp(3) with time zone,
    "salt" varchar,
    "hash" varchar,
    "reset_password_requested_at" timestamp(3) with time zone,
    "login_attempts" numeric DEFAULT 0,
    "lock_until" timestamp(3) with time zone
  );

  CREATE TABLE "website"."pages" (
    "id" serial PRIMARY KEY NOT NULL,
    "title" varchar NOT NULL,
    "slug" varchar NOT NULL,
    "summary" varchar,
    "content" jsonb,
    "updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
    "created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );

  CREATE TABLE "website"."services" (
    "id" serial PRIMARY KEY NOT NULL,
    "title" varchar NOT NULL,
    "slug" varchar NOT NULL,
    "summary" varchar,
    "content" jsonb,
    "cta" varchar,
    "coming_soon" boolean DEFAULT false,
    "updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
    "created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );

  CREATE TABLE "website"."track_record_items" (
    "id" serial PRIMARY KEY NOT NULL,
    "title" varchar NOT NULL,
    "role" varchar,
    "description" varchar,
    "updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
    "created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );

  CREATE TABLE "website"."team_members" (
    "id" serial PRIMARY KEY NOT NULL,
    "name" varchar NOT NULL,
    "role" varchar,
    "biography" varchar,
    "updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
    "created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );

  CREATE TABLE "website"."faqs" (
    "id" serial PRIMARY KEY NOT NULL,
    "question" varchar NOT NULL,
    "answer" varchar NOT NULL,
    "updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
    "created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );

  CREATE TABLE "website"."lead_submissions" (
    "id" serial PRIMARY KEY NOT NULL,
    "name" varchar NOT NULL,
    "organization" varchar,
    "phone" varchar,
    "email" varchar,
    "subject" varchar,
    "message" varchar,
    "source" varchar,
    "assigned_staff_id" integer,
    "status" "website"."enum_lead_submissions_status" DEFAULT 'new' NOT NULL,
    "updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
    "created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );

  CREATE TABLE "website"."media" (
    "id" serial PRIMARY KEY NOT NULL,
    "alt" varchar NOT NULL,
    "updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
    "created_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
    "url" varchar,
    "thumbnail_u_r_l" varchar,
    "filename" varchar,
    "mime_type" varchar,
    "filesize" numeric,
    "width" numeric,
    "height" numeric,
    "focal_x" numeric,
    "focal_y" numeric
  );

  CREATE TABLE "website"."payload_kv" (
    "id" serial PRIMARY KEY NOT NULL,
    "key" varchar NOT NULL,
    "data" jsonb NOT NULL
  );

  CREATE TABLE "website"."payload_locked_documents" (
    "id" serial PRIMARY KEY NOT NULL,
    "global_slug" varchar,
    "updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
    "created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );

  CREATE TABLE "website"."payload_locked_documents_rels" (
    "id" serial PRIMARY KEY NOT NULL,
    "order" integer,
    "parent_id" integer NOT NULL,
    "path" varchar NOT NULL,
    "staff_id" integer,
    "pages_id" integer,
    "services_id" integer,
    "track_record_items_id" integer,
    "team_members_id" integer,
    "faqs_id" integer,
    "lead_submissions_id" integer,
    "media_id" integer
  );

  CREATE TABLE "website"."payload_preferences" (
    "id" serial PRIMARY KEY NOT NULL,
    "key" varchar,
    "value" jsonb,
    "updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
    "created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );

  CREATE TABLE "website"."payload_preferences_rels" (
    "id" serial PRIMARY KEY NOT NULL,
    "order" integer,
    "parent_id" integer NOT NULL,
    "path" varchar NOT NULL,
    "staff_id" integer
  );

  CREATE TABLE "website"."payload_migrations" (
    "id" serial PRIMARY KEY NOT NULL,
    "name" varchar,
    "batch" numeric,
    "updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
    "created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );

  ALTER TABLE "website"."staff_sessions" ADD CONSTRAINT "staff_sessions_parent_id_fk" FOREIGN KEY ("_parent_id") REFERENCES "website"."staff"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "website"."lead_submissions" ADD CONSTRAINT "lead_submissions_assigned_staff_id_staff_id_fk" FOREIGN KEY ("assigned_staff_id") REFERENCES "website"."staff"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "website"."payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_parent_fk" FOREIGN KEY ("parent_id") REFERENCES "website"."payload_locked_documents"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "website"."payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_staff_fk" FOREIGN KEY ("staff_id") REFERENCES "website"."staff"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "website"."payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_pages_fk" FOREIGN KEY ("pages_id") REFERENCES "website"."pages"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "website"."payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_services_fk" FOREIGN KEY ("services_id") REFERENCES "website"."services"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "website"."payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_track_record_items_fk" FOREIGN KEY ("track_record_items_id") REFERENCES "website"."track_record_items"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "website"."payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_team_members_fk" FOREIGN KEY ("team_members_id") REFERENCES "website"."team_members"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "website"."payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_faqs_fk" FOREIGN KEY ("faqs_id") REFERENCES "website"."faqs"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "website"."payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_lead_submissions_fk" FOREIGN KEY ("lead_submissions_id") REFERENCES "website"."lead_submissions"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "website"."payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_media_fk" FOREIGN KEY ("media_id") REFERENCES "website"."media"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "website"."payload_preferences_rels" ADD CONSTRAINT "payload_preferences_rels_parent_fk" FOREIGN KEY ("parent_id") REFERENCES "website"."payload_preferences"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "website"."payload_preferences_rels" ADD CONSTRAINT "payload_preferences_rels_staff_fk" FOREIGN KEY ("staff_id") REFERENCES "website"."staff"("id") ON DELETE cascade ON UPDATE no action;
  CREATE INDEX "staff_sessions_order_idx" ON "website"."staff_sessions" USING btree ("_order");
  CREATE INDEX "staff_sessions_parent_id_idx" ON "website"."staff_sessions" USING btree ("_parent_id");
  CREATE INDEX "staff_updated_at_idx" ON "website"."staff" USING btree ("updated_at");
  CREATE INDEX "staff_created_at_idx" ON "website"."staff" USING btree ("created_at");
  CREATE UNIQUE INDEX "staff_email_idx" ON "website"."staff" USING btree ("email");
  CREATE UNIQUE INDEX "pages_slug_idx" ON "website"."pages" USING btree ("slug");
  CREATE INDEX "pages_updated_at_idx" ON "website"."pages" USING btree ("updated_at");
  CREATE INDEX "pages_created_at_idx" ON "website"."pages" USING btree ("created_at");
  CREATE UNIQUE INDEX "services_slug_idx" ON "website"."services" USING btree ("slug");
  CREATE INDEX "services_updated_at_idx" ON "website"."services" USING btree ("updated_at");
  CREATE INDEX "services_created_at_idx" ON "website"."services" USING btree ("created_at");
  CREATE INDEX "track_record_items_updated_at_idx" ON "website"."track_record_items" USING btree ("updated_at");
  CREATE INDEX "track_record_items_created_at_idx" ON "website"."track_record_items" USING btree ("created_at");
  CREATE INDEX "team_members_updated_at_idx" ON "website"."team_members" USING btree ("updated_at");
  CREATE INDEX "team_members_created_at_idx" ON "website"."team_members" USING btree ("created_at");
  CREATE INDEX "faqs_updated_at_idx" ON "website"."faqs" USING btree ("updated_at");
  CREATE INDEX "faqs_created_at_idx" ON "website"."faqs" USING btree ("created_at");
  CREATE INDEX "lead_submissions_assigned_staff_idx" ON "website"."lead_submissions" USING btree ("assigned_staff_id");
  CREATE INDEX "lead_submissions_updated_at_idx" ON "website"."lead_submissions" USING btree ("updated_at");
  CREATE INDEX "lead_submissions_created_at_idx" ON "website"."lead_submissions" USING btree ("created_at");
  CREATE INDEX "media_updated_at_idx" ON "website"."media" USING btree ("updated_at");
  CREATE INDEX "media_created_at_idx" ON "website"."media" USING btree ("created_at");
  CREATE UNIQUE INDEX "media_filename_idx" ON "website"."media" USING btree ("filename");
  CREATE UNIQUE INDEX "payload_kv_key_idx" ON "website"."payload_kv" USING btree ("key");
  CREATE INDEX "payload_locked_documents_global_slug_idx" ON "website"."payload_locked_documents" USING btree ("global_slug");
  CREATE INDEX "payload_locked_documents_updated_at_idx" ON "website"."payload_locked_documents" USING btree ("updated_at");
  CREATE INDEX "payload_locked_documents_created_at_idx" ON "website"."payload_locked_documents" USING btree ("created_at");
  CREATE INDEX "payload_locked_documents_rels_order_idx" ON "website"."payload_locked_documents_rels" USING btree ("order");
  CREATE INDEX "payload_locked_documents_rels_parent_idx" ON "website"."payload_locked_documents_rels" USING btree ("parent_id");
  CREATE INDEX "payload_locked_documents_rels_path_idx" ON "website"."payload_locked_documents_rels" USING btree ("path");
  CREATE INDEX "payload_locked_documents_rels_staff_id_idx" ON "website"."payload_locked_documents_rels" USING btree ("staff_id");
  CREATE INDEX "payload_locked_documents_rels_pages_id_idx" ON "website"."payload_locked_documents_rels" USING btree ("pages_id");
  CREATE INDEX "payload_locked_documents_rels_services_id_idx" ON "website"."payload_locked_documents_rels" USING btree ("services_id");
  CREATE INDEX "payload_locked_documents_rels_track_record_items_id_idx" ON "website"."payload_locked_documents_rels" USING btree ("track_record_items_id");
  CREATE INDEX "payload_locked_documents_rels_team_members_id_idx" ON "website"."payload_locked_documents_rels" USING btree ("team_members_id");
  CREATE INDEX "payload_locked_documents_rels_faqs_id_idx" ON "website"."payload_locked_documents_rels" USING btree ("faqs_id");
  CREATE INDEX "payload_locked_documents_rels_lead_submissions_id_idx" ON "website"."payload_locked_documents_rels" USING btree ("lead_submissions_id");
  CREATE INDEX "payload_locked_documents_rels_media_id_idx" ON "website"."payload_locked_documents_rels" USING btree ("media_id");
  CREATE INDEX "payload_preferences_key_idx" ON "website"."payload_preferences" USING btree ("key");
  CREATE INDEX "payload_preferences_updated_at_idx" ON "website"."payload_preferences" USING btree ("updated_at");
  CREATE INDEX "payload_preferences_created_at_idx" ON "website"."payload_preferences" USING btree ("created_at");
  CREATE INDEX "payload_preferences_rels_order_idx" ON "website"."payload_preferences_rels" USING btree ("order");
  CREATE INDEX "payload_preferences_rels_parent_idx" ON "website"."payload_preferences_rels" USING btree ("parent_id");
  CREATE INDEX "payload_preferences_rels_path_idx" ON "website"."payload_preferences_rels" USING btree ("path");
  CREATE INDEX "payload_preferences_rels_staff_id_idx" ON "website"."payload_preferences_rels" USING btree ("staff_id");
  CREATE INDEX "payload_migrations_updated_at_idx" ON "website"."payload_migrations" USING btree ("updated_at");
  CREATE INDEX "payload_migrations_created_at_idx" ON "website"."payload_migrations" USING btree ("created_at");`)
}

// Rolling back a baseline can destroy data. Restore a verified backup instead.
export async function down(): Promise<void> {
  throw new Error('Baseline rollback is disabled; restore a verified database and media backup.')
}
