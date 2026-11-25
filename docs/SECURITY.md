# Security and data privacy

These records describe minors' counseling, discipline and abuse cases. They are
sensitive personal information under RA 10173 (Data Privacy Act of 2012), and DO 006,
s. 2026 limits access to authorised school personnel and designated DepEd officials.
The design starts from that.

## Who sees what

Defined in `apps/core/roles.py`. Staff on the Child Protection Committee can be flagged
as CPC members, which adds case access to their role.

| | Admin | School Head | Counselor / Designate | LFO | Teacher | + CPC flag |
| --- | :-: | :-: | :-: | :-: | :-: | :-: |
| Learner profiles | all + confidential notes | all | all + confidential notes | all | own advisory class | |
| Counseling sessions and notes | ✓ | – | ✓ | – | – | |
| Violations / disciplinary cases | ✓ | ✓ | ✓ | ✓ | report; own reports and advisees | |
| Interventions | ✓ | view | ✓ | ✓ | – | |
| Protection (LRP) cases | ✓ incl. restricted | ✓ incl. restricted | ✓ incl. restricted | ✓ except restricted | report only | ✓ except restricted |
| Reports | ✓ | ✓ | ✓ | ✓ | – | LRP reports |
| Users, settings | ✓ | – | – | – | – | |
| Audit log | ✓ | ✓ | – | – | – | |

- The **System Administrator** is a super administrator: it holds every permission,
  including counseling notes and protection case files. Give this role only to the person
  accountable for the guidance office's records, use a strong unique password, and keep
  the number of admin accounts small. Every record view is still written to the audit log.
  Confidential models aren't registered in the Django admin at all.
- A **restricted** protection case (set automatically for sexual abuse, sexual
  exploitation and similar) is visible only to the School Head and guidance staff, and
  its deadline follow-ups are hidden from everyone else.
- A **restricted** counseling session opens only for the counselor who recorded it.
- A staff member who reports a concern sees its reference number and status, never the
  case file.
- Accounts are deactivated, never deleted, so the audit trail stays complete.

## Encryption

- Narratives and notes (counseling notes, case narratives, findings, risk factors,
  informant details, confidential profile fields, attachment names) are encrypted in the
  application with Fernet (AES-128 + HMAC-SHA256) before they reach the database.
  Supabase, its backups and anyone with database access see only ciphertext.
- Encrypted fields can't be searched; names, dates and categories stay searchable.
- Database connections require TLS. Supabase encrypts storage at rest.

## Audit trail

- Logged: sign-ins (and failures), sign-outs, every create/update/delete on learner,
  case, session and plan records, every view of a confidential record, every print,
  export and attachment download.
- Change logs record which encrypted fields changed but never their contents.
- `AuditEvent` rows can't be edited or deleted through Django, and a PostgreSQL trigger
  rejects `UPDATE`/`DELETE` even from the SQL editor.
- The School Head and the administrator can search and export the log (Admin → Audit log).

## Sign-in and sessions

- Passwords: at least 12 characters, checked against common passwords.
- 5 failed attempts lock that username + IP for 30 minutes (django-axes).
- Administrators set temporary passwords; users must change them on first sign-in.
- Sessions expire after 30 minutes idle and when the browser closes.

## Web hardening

- Strict Content-Security-Policy: scripts, styles and fonts only from the app itself
  (Bootstrap, Bootstrap Icons and HTMX are vendored, no CDNs). HTMX runs with eval off.
- HSTS, secure cookies, `X-Frame-Options: DENY`, same-origin referrer policy, CSRF
  protection including HTMX requests.
- Each request runs in one database transaction: a record, its audit entry and its
  follow-ups are saved together or not at all.
- Reports are de-identified (case numbers, sex, grade). Reminder emails carry follow-up
  titles only. Keep learners' names out of titles.

## Supabase-specific

- Django's tables live in a private `guidance` schema owned by a dedicated
  `guidance_app` role (see `supabase/setup.sql`); `anon` and `authenticated` have no
  access, and the Data API should be switched off.
- Storage S3 keys bypass Storage RLS: keep them in Vercel environment variables only.
  Files are fetched server-side after a permission check; buckets stay private.

## Things the school still has to do

- Have the Data Protection Officer review the system and record it in the school's
  data inventory; DepEd is NPC-registered (DM 008, s. 2026).
- Decide a retention period for closed cases (DO 006 sets none) and a disposal process.
- Give access only to people with a role in the guidance and child-protection process,
  and review the user list each school year.
- Consider adding two-factor authentication for counselors and the School Head before
  go-live (django-allauth's MFA or django-otp fit this stack).
