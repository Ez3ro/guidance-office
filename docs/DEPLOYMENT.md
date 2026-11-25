# Deploying on Vercel + Supabase

The app runs as a single Vercel Function in Singapore (`sin1`, set in `vercel.json`),
talking to a Supabase project in the same region. Plan on about an hour the first time.

## 1. Supabase

1. Create a project in **Southeast Asia (Singapore)**. For real learner records use the
   **Pro** plan: Free projects pause after about a week of low activity and have no
   backups.
2. **Project Settings → Data API → switch the Data API off.** The app never uses it.
3. **SQL Editor:** paste [`supabase/setup.sql`](../supabase/setup.sql), replace the
   password with a long random one, and run it. This creates the `guidance_app` role and
   a private `guidance` schema that the Data API can't expose.
4. **Connect → Transaction pooler**: copy the connection string, then change the user to
   `guidance_app.<project-ref>` and the password to the one you chose:

   ```
   postgresql://guidance_app.<project-ref>:<password>@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
   ```

   Port 6543 is the transaction pooler, which suits serverless functions. The app
   detects it and switches off server-side cursors automatically.
5. **Storage (for attachments):** create a **private** bucket called `guidance-files`.
   Under Storage → S3 Configuration, turn on the S3 protocol, note the endpoint and
   region, and create an access key pair. These keys bypass Storage RLS, so they only
   ever go into Vercel's environment variables.

## 2. Vercel

1. **Add New → Project → import the GitHub repository.** Vercel detects Django from
   `manage.py`; leave the build settings alone.
2. Add these **Environment Variables**, scoped to **Production** only:

   | Variable | Value |
   | --- | --- |
   | `DJANGO_SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
   | `FIELD_ENCRYPTION_KEYS` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. **Save a copy in a password manager.** |
   | `DATABASE_URL` | the transaction pooler URL from step 1.4 |
   | `CRON_SECRET` | another long random string |
   | `SITE_NAME` | e.g. `Guidance Office – Sample NHS` |
   | `STORAGE_S3_BUCKET` | `guidance-files` |
   | `STORAGE_S3_ENDPOINT_URL` | `https://<project-ref>.storage.supabase.co/storage/v1/s3` |
   | `STORAGE_S3_REGION` | the region shown on the S3 page, e.g. `ap-southeast-1` |
   | `STORAGE_S3_ACCESS_KEY_ID` / `STORAGE_S3_SECRET_ACCESS_KEY` | the S3 key pair |
   | `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | optional, for reminder emails |
   | `DJANGO_ALLOWED_HOSTS` | only if you add a custom domain (the `*.vercel.app` hosts are picked up automatically) |

3. **Deploy.** The build runs `build.py`, which runs Django's deploy checks and applies
   migrations (production builds only), then Vercel collects static files.
4. Create the first administrator from your own computer, pointing at the production
   database:

   ```bash
   DATABASE_URL="<the pooler URL>" FIELD_ENCRYPTION_KEYS="<key>" DJANGO_SECRET_KEY=x \
     python manage.py seed_reference_data
   DATABASE_URL="<the pooler URL>" FIELD_ENCRYPTION_KEYS="<key>" DJANGO_SECRET_KEY=x \
     python manage.py createsuperuser
   ```

5. Sign in, then: **Admin → School profile** (printed on every form), **Admin →
   Reference data** to add the school year and sections, check the offence list against
   Annex I, and **Admin → Users** to add staff with temporary passwords.

## 3. Behaviour on Vercel worth knowing

- **Preview deployments are switched off** (`ignoreCommand` in `vercel.json`), so a
  branch preview can never touch production data. To enable previews, give the Preview
  environment its own Supabase project and remove `ignoreCommand`.
- **Uploads are capped at 4 MB** because Vercel Functions accept request bodies up to
  4.5 MB. Downloads stream through Django so every one is permission-checked and logged.
- **Reminders** run once a day at 07:00 Manila time (`0 23 * * *` UTC). Vercel sends
  `CRON_SECRET` as a bearer token; without it the endpoint refuses to run. On the Hobby
  plan cron runs once a day and may fire any time within the hour.
- **Sessions** end after 30 minutes of inactivity (`SESSION_IDLE_TIMEOUT_MINUTES`).

## 4. Backups and keys

- Supabase Pro keeps daily backups. Test a restore once before relying on it.
- Encrypted fields need `FIELD_ENCRYPTION_KEYS` to be read, including from a backup.
- To rotate the key: put the new key first and the old key second
  (`FIELD_ENCRYPTION_KEYS=new,old`), redeploy, run
  `python manage.py rotate_encryption_keys` against production, then remove the old key.

## Moving off Vercel later

Nothing is Vercel-specific apart from `vercel.json` and `build.py`. The app runs on any
host that can run a Django WSGI app with a Postgres `DATABASE_URL` (Render, Railway, a
VPS): run `migrate` on deploy and schedule `python manage.py send_followup_reminders`
daily.
