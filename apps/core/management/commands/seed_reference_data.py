"""Loads starter reference lists. Safe to run more than once.

The offence list and levels follow published summaries of DO 006, s. 2026 (Annex I)
and must be checked against the signed issuance and the school's own rules
before use. Edit them in Admin → Reference data.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.discipline.models import OffenseType, Sanction
from apps.interventions.models import InterventionType
from apps.protection.models import ConcernCategory, ConcernType, ReferralAgency

CONCERNS = [
    (ConcernCategory.BULLYING, "Physical bullying", False),
    (ConcernCategory.BULLYING, "Verbal bullying", False),
    (ConcernCategory.BULLYING, "Social / relational bullying", False),
    (ConcernCategory.BULLYING, "Cyberbullying", False),
    (ConcernCategory.BULLYING, "Gender-based bullying", False),
    (ConcernCategory.CHILD_ABUSE, "Physical abuse", False),
    (ConcernCategory.CHILD_ABUSE, "Psychological / emotional abuse", False),
    (ConcernCategory.CHILD_ABUSE, "Sexual abuse", True),
    (ConcernCategory.CHILD_ABUSE, "Neglect", False),
    (ConcernCategory.VIOLENCE, "Physical violence", False),
    (ConcernCategory.VIOLENCE, "Threats / psychological violence", False),
    (ConcernCategory.VIOLENCE, "Sexual violence", True),
    (ConcernCategory.EXPLOITATION, "Sexual exploitation, including online (OSAEC)", True),
    (ConcernCategory.EXPLOITATION, "Economic exploitation / child labour", False),
    (
        ConcernCategory.DISCRIMINATION,
        "Discrimination (sex, SOGIE, religion, disability, pregnancy, HIV status, ethnicity, CICL status)",
        False,
    ),
    (ConcernCategory.GBSH, "Gender-based sexual harassment", True),
    (ConcernCategory.CYBER, "Sharing of intimate or demeaning images or videos", True),
    (ConcernCategory.CYBER, "Other online harm", False),
    (ConcernCategory.CORPORAL_PUNISHMENT, "Corporal punishment by school personnel", False),
    (ConcernCategory.CORPORAL_PUNISHMENT, "Humiliating or degrading discipline", False),
    (ConcernCategory.OTHER, "Other learner rights and protection concern", False),
]

CHECK = "Check against DO 006, s. 2026 Annex I and the school's rules."
LEVEL_RESPONSE = {
    1: "Progressive: written reprimand, parent/guardian summons (call slip), then suspension. "
    + CHECK,
    2: "1st offence: suspension; 2nd: non-readmission; 3rd: exclusion. Due process required. "
    + CHECK,
    3: (
        "Preventive suspension; up to non-readmission or exclusion; automatic referral to law "
        "enforcement and other agencies. Due process required. " + CHECK
    ),
}
DEVICE_RESPONSE = (
    "Annex G: 1st offence – confiscated, returned at the end of the subject period; 2nd – kept "
    "until the end of class hours and parent notified; 3rd onwards – deposited with the School "
    "Head and released to the parent or guardian."
)

OFFENSES = [
    ("L1-01", "Swearing or profanity on school premises", 1, {}),
    ("L1-02", "Simple vandalism", 1, {}),
    ("L1-03", "Disruptive behaviour", 1, {}),
    ("L1-04", "Spreading false information that causes confusion or commotion", 1, {}),
    ("L1-05", "Unauthorised use of a portable device", 1, {"is_device_related": True}),
    ("L2-01", "Stalking", 2, {}),
    ("L2-02", "Slight physical injuries", 2, {}),
    ("L2-03", "Theft", 2, {}),
    ("L2-04", "Intimidation", 2, {}),
    ("L2-05", "Harassment", 2, {}),
    (
        "L2-06",
        "Bullying (handled under the school's anti-bullying policy)",
        2,
        {"is_bullying": True},
    ),
    ("L3-01", "Bomb threat or bomb joke", 3, {}),
    ("L3-02", "Bringing a deadly weapon", 3, {}),
    ("L3-03", "Hazing", 3, {}),
    ("L3-04", "Sexual assault", 3, {}),
    ("L3-05", "Acts of lasciviousness", 3, {}),
    ("L3-06", "Inflicting serious physical injuries", 3, {}),
    ("L3-07", "Bringing illegal drugs or liquor", 3, {}),
    ("L3-08", "Joining a street gang", 3, {}),
    ("L3-09", "Sharing demeaning or obscene videos of oneself or others", 3, {}),
    ("L3-10", "Cheating during examinations", 3, {}),
    ("L3-11", "Murder or homicide", 3, {}),
]

SANCTIONS = [
    (
        "Conference with the learner",
        "Positive discipline: talk through the behaviour and agree next steps.",
        False,
    ),
    ("Written reprimand", "", False),
    ("Parent / guardian conference (call slip)", "Annex K call slip.", False),
    ("Temporary confiscation of device", "Progressive sanctions under Annex G.", False),
    (
        "Formative / restorative activity",
        "Positive, non-humiliating activity that repairs harm.",
        False,
    ),
    ("Preventive suspension", "Interim measure while a grave case is investigated.", False),
    ("Suspension", "", True),
    ("Non-readmission", "Learner may finish the current school year but not enrol the next.", True),
    (
        "Exclusion",
        "Learner is removed from the class list; learning continues only through approved interventions.",
        True,
    ),
    ("Referral to law enforcement / appropriate agency", "", False),
]

INTERVENTIONS = [
    "Individual counseling",
    "Group counseling",
    "Parent / guardian conference",
    "Home visitation",
    "Behavioural contract",
    "Mentoring / peer support",
    "Academic support / tutorial",
    "Psychological first aid (PFA)",
    "Mental health and psychosocial support (MHPSS) referral",
    "Referral to external agency",
    "Life skills / values formation session",
    "Safety plan",
]

AGENCIES = [
    ("DSWD Field Office", ReferralAgency.AgencyType.SOCIAL_WELFARE),
    (
        "City / Municipal Social Welfare and Development Office (C/MSWDO)",
        ReferralAgency.AgencyType.SOCIAL_WELFARE,
    ),
    ("PNP Women and Children Protection Desk (WCPD)", ReferralAgency.AgencyType.LAW_ENFORCEMENT),
    ("National Bureau of Investigation (NBI)", ReferralAgency.AgencyType.LAW_ENFORCEMENT),
    ("Barangay Council for the Protection of Children (BCPC)", ReferralAgency.AgencyType.BARANGAY),
    ("Barangay VAW Desk", ReferralAgency.AgencyType.BARANGAY),
    ("Women and Children Protection Unit (WCPU), hospital", ReferralAgency.AgencyType.HEALTH),
    ("Rural Health Unit / City Health Office", ReferralAgency.AgencyType.HEALTH),
    ("Psychologist / psychiatrist", ReferralAgency.AgencyType.MENTAL_HEALTH),
    ("Schools Division Office – LRP focal person", ReferralAgency.AgencyType.DEPED),
    ("Public Attorney's Office (PAO)", ReferralAgency.AgencyType.LEGAL),
    ("Commission on Human Rights (CHR)", ReferralAgency.AgencyType.OTHER),
]


class Command(BaseCommand):
    help = "Loads concern types, offences (DO 006 levels), sanctions, intervention types and referral agencies."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        for category, name, sensitive in CONCERNS:
            _, new = ConcernType.objects.get_or_create(
                category=category, name=name, defaults={"is_sensitive": sensitive}
            )
            created += new
        for code, name, level, extra in OFFENSES:
            response = DEVICE_RESPONSE if extra.get("is_device_related") else LEVEL_RESPONSE[level]
            _, new = OffenseType.objects.get_or_create(
                code=code,
                defaults={"name": name, "level": level, "default_response": response, **extra},
            )
            created += new
        for name, description, due_process in SANCTIONS:
            _, new = Sanction.objects.get_or_create(
                name=name,
                defaults={"description": description, "requires_due_process": due_process},
            )
            created += new
        for name in INTERVENTIONS:
            _, new = InterventionType.objects.get_or_create(name=name)
            created += new
        for name, agency_type in AGENCIES:
            _, new = ReferralAgency.objects.get_or_create(
                name=name, defaults={"agency_type": agency_type}
            )
            created += new
        self.stdout.write(self.style.SUCCESS(f"Reference data loaded ({created} new item(s))."))
        self.stdout.write(
            "Review the offence list and levels against the signed DO 006, s. 2026 Annex I "
            "and your school's rules (Admin → Reference data)."
        )
