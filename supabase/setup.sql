-- One-time Supabase setup for the Guidance Office Management System.
-- Run in the Supabase Dashboard → SQL Editor (as the default postgres user).
--
-- What it does:
--   * creates a dedicated login role for Django (least privilege: it can't touch
--     Supabase's auth, storage or public schemas), and
--   * gives Django a private schema, "guidance". Supabase's Data API (REST/GraphQL)
--     only exposes the schemas listed under Project Settings → Data API ("public" by
--     default), so nothing Django creates here is reachable with the anon or
--     publishable key, even if someone re-enables the Data API later.
--
-- After running it, also switch the Data API off entirely
-- (Project Settings → Data API), since this app never uses it.

-- 1. Replace the password with a long random one (e.g. 40+ characters from a password
--    manager) and keep it there. You'll put it in Vercel's DATABASE_URL.
create role guidance_app with login password 'REPLACE-WITH-A-LONG-RANDOM-PASSWORD';

-- 2. Private schema for all of Django's tables.
create schema if not exists guidance;
grant usage, create on schema guidance to guidance_app;

-- 3. Django creates and finds its tables through the role's search_path.
--    Set at role level so it also works through the transaction pooler.
alter role guidance_app set search_path = guidance;

-- 4. Make sure Supabase's API roles have nothing on the private schema.
revoke all on schema guidance from anon, authenticated;

-- Connection string for Vercel (Dashboard → Connect → Transaction pooler, then swap the user):
--   postgresql://guidance_app.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
