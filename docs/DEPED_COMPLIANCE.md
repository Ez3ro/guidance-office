# DepEd policy mapping

How the system follows **DO 40, s. 2012** (DepEd Child Protection Policy) and
**DO 006, s. 2026** (Guidelines on Ensuring a Safe and Motivating Learning Environment,
issued 24 March 2026). DO 006 harmonises learner-protection issuances: it supplements
DO 40 rather than repealing it. It expressly repeals DO 6, s. 1954 (hazing) and the
1999, 2000 and 2003 phone-use orders.

> **Important.** This mapping was built from published summaries of DO 006, s. 2026, not
> from the signed PDF and its annexes. Before using the forms officially, compare each
> item marked **Verify** with the signed issuance (deped.gov.ph, `DO_s2026_006r.pdf`)
> and adjust the templates in `templates/printable/` and the reference data.

## Case handling (DO 006 flow)

| Step in the order | In the system | Status |
| --- | --- | --- |
| Probable LRP incident identified; CPC (through the RGC, a learner formation officer or the school head) completes the Initial Risk Assessment Form (Annex H) | Case → **Risk assessment**: probability, impact, overall level, immediate needs, actions, responsible persons, timeline. Printable. | Fields follow the published description of Annex H. **Verify** the annex layout. |
| Incident Report and Intake Sheet identifying victim and respondent and initial interventions, referred to the disciplining authority **within 48 hours** | Case intake + parties; printable intake sheet; 48-hour follow-up created automatically and marked met/missed | Built. **Verify** whether DepEd prescribes a specific template. |
| Substantiated reports go to fact-finding; findings to the School Head **within 10 calendar days** | Fact-finding start date → 10-day follow-up; printable fact-finding report | The 10 days are counted from the date fact-finding starts. **Verify** the reference point. |
| School Head forwards results to the SDS and RD **within 30 calendar days** of receiving the report | 30-day follow-up from the report date, created once fact-finding starts | Built. |
| Penalised cases: written notice, **10 calendar days** to answer, written decision | Disciplinary case due-process fields and follow-ups | Built. |
| Appeals to the SDS or RD **within 15 days**; bullying appeals to OULLA **within 10 days** | Appeal deadline and body computed from the decision date | Built. |
| Confidential records kept by the RGC or designated CPC personnel; access limited to authorised personnel; RA 10173 applies | Role-based access, restricted cases, encryption, audit log | Built. See SECURITY.md. |
| Centralised incident database and regular audits | The case register plus the audit log and deadline compliance report | Built. |

There is no deadline in DO 006 for the risk assessment itself; the system uses a
school-set target of 24 hours (`LRP_RISK_ASSESSMENT_TARGET_HOURS`).

The order refers to a "disciplining authority" without defining it, so the case records
the name and position of whoever the intake was referred to.

## Process flows

Cases are classified by the DO 006 annex that applies: Annex A (school personnel or
another adult), Annex B (learner to learner), Annex C (learner to community). **Verify**
the steps in each annex; the system currently applies the same timeline to all three.

## Reports and forms

| Required by DO 006 (as summarised) | In the system |
| --- | --- |
| Annual bullying report to the SDO, first week of the school year | Reports → Annual Report on Bullying Incidents (by type, grade and sex; respondents; status; referrals). **Verify** the SDO's template. |
| Case summary reports to the Division LRP focal person | Reports → LRP Case Summary Report (de-identified case list and counts) |
| Annex F – confiscation slip (prohibited items) | Violation → Confiscation slip |
| Annex J – confiscation slip (portable devices) | Violation → Confiscation slip, with the Annex G progressive release rules |
| Annex K – call slip to parents/guardians | Violation, disciplinary case or protection case → Call slip |
| Annex H – Initial Risk Assessment | Case → Risk assessment → Print |
| Annex D – localised anti-bullying policy template | Not in the system (a policy document, not a record). |
| Annex E – random routine bag inspection school plan | Not in the system yet. |

## Offence classification (Annex I)

The starter offence list (`python manage.py seed_reference_data`) uses the three levels
as reported in DepEd's July 2026 announcements:

- **First level**: swearing, simple vandalism, disruptive behaviour, spreading false
  information causing commotion.
- **Second level**: stalking, slight physical injuries, theft, intimidation, harassment.
- **Third level**: bomb threats or jokes, deadly weapons, hazing, sexual assault, acts of
  lasciviousness, serious physical injuries, illegal drugs or liquor, street gangs,
  sharing demeaning or obscene videos, cheating during examinations, murder.

**Verify** every item and level against Annex I. Cheating during examinations appearing
at the third level comes from news coverage and is the item most worth double-checking.
Edit the list in Admin → Reference data → Offense types.

## DO 40, s. 2012

- **Child Protection Committee**: CPC membership is a flag on each staff account; the
  School Head (chair) and guidance staff always have case access.
- **Prohibited acts and definitions**: the concern types (child abuse, exploitation,
  violence, discrimination, bullying, corporal punishment and others) can be edited in
  Admin → Reference data → Concern types.
- **Referral to agencies** (DSWD/LSWDO, PNP-WCPD, BCPC, health facilities): case →
  Referrals, with status and agency feedback.
- **Positive discipline**: sanctions list excludes corporal and humiliating punishment;
  the case page reminds users of the rule.

## Related law and issuances to keep in mind

- RA 10627 (Anti-Bullying Act of 2013) and its IRR; DO 55, s. 2013 (not repealed by
  DO 006).
- RA 7610 (special protection of children), RA 9344 (Juvenile Justice and Welfare Act)
  for children at risk and children in conflict with the law.
- RA 9258 (Guidance and Counseling Act of 2004) on confidentiality of counseling.
- RA 10173 (Data Privacy Act of 2012).
- DO 009, s. 2026 (three-term school calendar): reports accept any date range, so
  term-based reporting works by choosing the term's dates.
