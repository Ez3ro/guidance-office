# Guidance Office Management System

A Django web app for a DepEd school's guidance office: learner guidance profiles,
discipline, counseling documentation, interventions, child protection intake and the
reports DepEd asks for, with an audit trail of who saw and changed what.

Built for one school, deployed on **Vercel** (Django as a Vercel Function, Singapore
region) with **Supabase** Postgres and Storage. Server-rendered Django templates with
HTMX; no separate frontend build.

## What's in it

| Module | What it does |
| --- | --- |
| **Learner guidance profiles** | LRN, family background, 4Ps/IP/LWD flags, interests; encrypted confidential notes for guidance staff only. Sections and enrolment per school year. |
| **Violation records & disciplinary cases** | Offence catalogue with the three DO 006, s. 2026 levels; offence count per school year for progressive sanctions (Annex G for devices); disciplinary cases with written notice, 10-day answer period, written decision and 15-day appeal (10 days to OULLA for bullying). |
| **Intervention management** | Intervention plans with goals, review dates, outcomes and progress notes, linked to the violation or case that prompted them. |
| **Counseling session documentation** | Individual, group, family and crisis sessions; notes and action plans encrypted at rest; "restricted" sessions only their counselor can open. |
| **Child protection intake** | DO 40, s. 2012 as harmonised by DO 006, s. 2026: case intake, people involved, Initial Risk Assessment (Annex H), referrals to DSWD/PNP-WCPD/BCPC and others, fact-finding, and the 48-hour / 10-day / 30-day timelines tracked automatically. Any staff member can "Report a concern". |
| **Guidance calendar & follow-ups** | Month calendar of events, sessions and deadlines; follow-up tracker with overdue flags; daily reminder email via Vercel Cron. |
| **Official reports** | LRP Case Summary (Division LRP focal person), Annual Report on Bullying Incidents (SDO), deadline compliance, guidance services and discipline summaries; print or download Excel. Printable Incident Report and Intake Sheet, Annex H, fact-finding report, call slip (Annex K) and confiscation slips (Annexes F and J). |
| **Case history & timeline** | One timeline per learner across every module, filtered to what the viewer's role allows. |
| **Audit log & user management** | Append-only log of sign-ins, views, changes, prints and exports (a database trigger blocks edits); role-based users; temporary passwords; lockout after 5 failed sign-ins. |

## Quick start (local)

Requires Python 3.13.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # DJANGO_DEBUG=true is enough for local use
python manage.py migrate
python manage.py seed_demo_data    # fictional school, users and records
python manage.py runserver
```

Open http://127.0.0.1:8000 and sign in as `counselor`, `principal`, `lfo`, `teacher1`,
`teacher2` (CPC member) or `admin`, password `Demo-Guidance-2026!`. Each role sees a
different slice of the system.

For a real start instead of demo data: `python manage.py seed_reference_data`, then
`python manage.py createsuperuser`, then set the school profile and school year.

Run the tests with `python manage.py test` (41 tests; they also pass on PostgreSQL).

## Deploying

See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** for the step-by-step Vercel + Supabase
setup: the one-time SQL script, environment variables, storage, cron and first sign-in.

## Before using it with real learners

1. **Check the forms against the signed DO 006, s. 2026.** The annex layouts and the
   offence list were built from published summaries of the order, not the signed PDF.
   See [docs/DEPED_COMPLIANCE.md](docs/DEPED_COMPLIANCE.md) for exactly what to verify.
2. **Use paid tiers for production data.** Supabase Free pauses inactive projects and
   has no backups; Vercel's Hobby plan is for non-commercial personal use.
3. **Keep the encryption key safe.** Losing `FIELD_ENCRYPTION_KEYS` means losing every
   encrypted note. Store it in a password manager as well as Vercel.
4. **Get the school's Data Protection Officer to sign off.** These are sensitive personal
   records of minors under RA 10173. See [docs/SECURITY.md](docs/SECURITY.md).

## Project layout

```
config/            settings, URLs, WSGI entrypoint (Vercel loads config/wsgi.py)
apps/core/         roles, encryption, generic views, attachments, dashboard, cron
apps/accounts/     users, roles, password change, user management
apps/audit/        append-only audit log and viewer
apps/students/     school years, sections, learners, timeline
apps/discipline/   offences, violations, disciplinary cases, sanctions
apps/counseling/   counseling sessions
apps/interventions/ intervention plans and progress notes
apps/protection/   LRP / child protection cases, risk assessment, referrals
apps/scheduling/   calendar, follow-ups, reminder digest
apps/reports/      report builders, Excel export, printable forms
templates/ static/ server-rendered UI (Bootstrap 5 + HTMX, vendored, strict CSP)
supabase/setup.sql one-time database setup (private schema + app role)
```

Access is decided in one place, `apps/core/roles.py`.
