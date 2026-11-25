"""Fictional demo data for trying the system locally. Never run against real records."""

import datetime
import random

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.core.models import SchoolProfile
from apps.core.roles import Role
from apps.counseling.models import CounselingSession
from apps.discipline.models import DisciplinaryCase, OffenseType, ViolationRecord
from apps.interventions.models import InterventionPlan, InterventionType
from apps.protection.models import CaseParty, ConcernType, ProtectionCase, RiskAssessment
from apps.scheduling.models import CalendarEvent
from apps.students.models import Enrollment, SchoolYear, Section, Student

DEMO_PASSWORD = "Demo-Guidance-2026!"

FIRST = [
    "Andrea",
    "Miguel",
    "Bea",
    "Carlo",
    "Denise",
    "Enzo",
    "Francine",
    "Gabriel",
    "Hannah",
    "Ivan",
    "Jasmine",
    "Kyle",
    "Lara",
    "Marco",
    "Nicole",
    "Oscar",
    "Patricia",
    "Rafael",
    "Sofia",
    "Tristan",
    "Uma",
    "Vince",
    "Wena",
    "Xian",
]
LAST = [
    "Dela Cruz",
    "Santos",
    "Reyes",
    "Garcia",
    "Mendoza",
    "Bautista",
    "Villanueva",
    "Ramos",
    "Aquino",
    "Navarro",
    "Castillo",
    "Flores",
]
MIDDLE = ["Lopez", "Torres", "Rivera", "Cruz", "Gomez", "Diaz"]


class Command(BaseCommand):
    help = "Creates fictional users, learners and records for a local demo."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG is off.")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError("Demo data is for local use. Pass --force if you really mean it.")
        if Student.objects.exists():
            raise CommandError(
                "Learners already exist; demo data is only loaded into an empty database."
            )
        random.seed(2026)
        call_command("seed_reference_data", stdout=self.stdout)

        school = SchoolProfile.load()
        school.name = "Sample National High School"
        school.school_id = "300000"
        school.district = "District I"
        school.division = "Schools Division of Sample City"
        school.region = "Region III – Central Luzon"
        school.address = "Sample Street, Sample City"
        school.school_head_name = "Dr. Maria Example"
        school.guidance_head_name = "Ms. Ana Counselor, RGC"
        school.save()

        User = get_user_model()

        def user(username, first, last, role, **extra):
            u = User(
                username=username,
                first_name=first,
                last_name=last,
                role=role,
                email=f"{username}@example.com",
                **extra,
            )
            u.set_password(DEMO_PASSWORD)
            u.save()
            return u

        admin = user("admin", "Sam", "Admin", Role.ADMIN, position="ICT Coordinator")
        head = user(
            "principal", "Maria", "Example", Role.SCHOOL_HEAD, position="School Principal II"
        )
        counselor = user(
            "counselor", "Ana", "Counselor", Role.COUNSELOR, position="Guidance Counselor I"
        )
        designate = user(
            "designate", "Ben", "Designate", Role.GUIDANCE_DESIGNATE, position="Teacher III"
        )
        lfo = user("lfo", "Lito", "Formation", Role.LFO, position="Learner Formation Officer")
        advisers = [
            user("teacher1", "Carla", "Adviser", Role.TEACHER, position="Teacher I"),
            user(
                "teacher2",
                "Dan",
                "Adviser",
                Role.TEACHER,
                position="Teacher II",
                is_cpc_member=True,
            ),
            user("teacher3", "Eva", "Adviser", Role.TEACHER, position="Teacher I"),
            user("teacher4", "Fe", "Adviser", Role.TEACHER, position="Master Teacher I"),
        ]

        today = timezone.localdate()
        start_year = today.year if today.month >= 6 else today.year - 1
        sy = SchoolYear.objects.create(
            name=f"{start_year}-{start_year + 1}",
            start_date=datetime.date(start_year, 6, 15),
            end_date=datetime.date(start_year + 1, 3, 31),
            is_current=True,
        )
        sections = [
            Section.objects.create(school_year=sy, grade_level=g, name=n, adviser=a)
            for (g, n), a in zip(
                [("7", "Sampaguita"), ("8", "Narra"), ("9", "Molave"), ("10", "Acacia")],
                advisers,
                strict=True,
            )
        ]

        students = []
        for i, first in enumerate(FIRST):
            s = Student.objects.create(
                lrn=f"1{random.randint(10**10, 10**11 - 1)}",
                first_name=first,
                last_name=random.choice(LAST),
                middle_name=random.choice(MIDDLE),
                sex="F" if i % 2 == 0 else "M",
                birth_date=datetime.date(
                    start_year - 13 - (i % 4), random.randint(1, 12), random.randint(1, 28)
                ),
                barangay="Poblacion",
                municipality="Sample City",
                province="Sample Province",
                guardian_name=f"Parent of {first}",
                guardian_relationship="Mother" if i % 3 else "Father",
                guardian_contact="0917 000 0000",
                living_with=random.choice(["both", "mother", "grandparents"]),
                is_4ps_beneficiary=i % 5 == 0,
                interests="Basketball, drawing" if i % 2 else "Reading, singing",
            )
            Enrollment.objects.create(
                student=s, section=sections[i % 4], date_enrolled=sy.start_date
            )
            students.append(s)

        offenses = {o.code: o for o in OffenseType.objects.all()}
        for code, idx, days_ago in [
            ("L1-03", 1, 40),
            ("L1-05", 2, 30),
            ("L1-05", 2, 12),
            ("L2-04", 3, 20),
            ("L1-01", 5, 8),
            ("L2-06", 6, 5),
        ]:
            ViolationRecord.objects.create(
                student=students[idx],
                offense_type=offenses[code],
                incident_date=today - datetime.timedelta(days=days_ago),
                location="Classroom",
                description="Fictional demo incident.",
                reported_by=advisers[idx % 4],
                confiscation=ViolationRecord.Confiscation.DEVICE if code == "L1-05" else "",
                confiscated_item="Mobile phone" if code == "L1-05" else "",
            )

        case = DisciplinaryCase.objects.create(
            title="Intimidation of a classmate",
            summary="Fictional demo case.",
            handled_by=lfo,
            notice_served_on=today - datetime.timedelta(days=4),
            status=DisciplinaryCase.Status.NOTICE_SERVED,
        )
        case.respondents.add(students[3])
        ViolationRecord.objects.filter(student=students[3]).update(
            disciplinary_case=case, status=ViolationRecord.Status.ESCALATED
        )

        concerns = {c.name: c for c in ConcernType.objects.all()}
        bullying = ProtectionCase.objects.create(
            reported_at=timezone.now() - datetime.timedelta(hours=30),
            received_by=counselor,
            report_channel=ProtectionCase.Channel.TEACHER,
            informant_name="Ms. Carla Adviser",
            informant_relationship="Class adviser",
            incident_date=today - datetime.timedelta(days=2),
            narrative="Fictional demo report of repeated name-calling in a group chat.",
            flow=ProtectionCase.Flow.LEARNER_TO_LEARNER,
        )
        bullying.concern_types.set([concerns["Cyberbullying"], concerns["Verbal bullying"]])
        CaseParty.objects.create(case=bullying, role=CaseParty.Role.VICTIM, student=students[6])
        CaseParty.objects.create(case=bullying, role=CaseParty.Role.RESPONDENT, student=students[7])
        RiskAssessment.objects.create(
            case=bullying,
            assessed_by=counselor,
            risk_factors="Fictional: repeated messages, learner reluctant to attend class.",
            probability=RiskAssessment.Level.MEDIUM,
            impact=RiskAssessment.Level.MEDIUM,
            needs_pfa=True,
            parents_notified=True,
            actions_needed="Fictional: PFA, parent conference, monitor group chat with adviser.",
            responsible_persons="Guidance counselor; class adviser",
            timeline="Within the week",
        )

        restricted = ProtectionCase.objects.create(
            reported_at=timezone.now() - datetime.timedelta(hours=6),
            received_by=counselor,
            report_channel=ProtectionCase.Channel.DISCLOSURE,
            narrative="Fictional restricted demo case.",
            flow=ProtectionCase.Flow.ADULT_TO_LEARNER,
        )
        restricted.concern_types.set([concerns["Sexual abuse"]])
        restricted.restricted = True
        restricted.save()
        CaseParty.objects.create(case=restricted, role=CaseParty.Role.VICTIM, student=students[10])

        for i, concern in enumerate(
            ["academic", "personal_social", "family", "wellbeing", "career"]
        ):
            session = CounselingSession.objects.create(
                counselor=counselor if i % 2 == 0 else designate,
                session_date=today - datetime.timedelta(days=3 * i + 1),
                start_time=datetime.time(9 + i, 0),
                duration_minutes=45,
                primary_concern=concern,
                referral_source="teacher" if i % 2 else "self",
                consent_obtained=True,
                notes="Fictional demo session notes.",
                action_plan="Fictional follow-up plan.",
                next_session_date=today + datetime.timedelta(days=7 + i) if i < 2 else None,
                protection_case=bullying if concern == "personal_social" else None,
            )
            session.students.add(students[6] if concern == "personal_social" else students[i + 12])
        upcoming = CounselingSession.objects.create(
            counselor=counselor,
            session_date=today + datetime.timedelta(days=2),
            start_time=datetime.time(10, 30),
            primary_concern="wellbeing",
            status=CounselingSession.Status.SCHEDULED,
        )
        upcoming.students.add(students[6])

        types = {t.name: t for t in InterventionType.objects.all()}
        InterventionPlan.objects.create(
            student=students[6],
            intervention_type=types["Mentoring / peer support"],
            title="Peer support after cyberbullying report",
            goals="Fictional: learner reports feeling safe in class within 4 weeks.",
            responsible=counselor,
            status=InterventionPlan.Status.ONGOING,
            target_end_date=today + datetime.timedelta(days=21),
            protection_case=bullying,
        )
        InterventionPlan.objects.create(
            student=students[3],
            intervention_type=types["Behavioural contract"],
            title="Behavioural contract",
            goals="Fictional: no repeat intimidation incidents this term.",
            responsible=lfo,
            status=InterventionPlan.Status.PLANNED,
            target_end_date=today + datetime.timedelta(days=30),
            disciplinary_case=case,
        )

        event = CalendarEvent.objects.create(
            title="CPC meeting",
            event_type=CalendarEvent.EventType.CPC_MEETING,
            start=timezone.make_aware(
                datetime.datetime.combine(today + datetime.timedelta(days=1), datetime.time(14, 0))
            ),
            location="Principal's office",
            visibility=CalendarEvent.Visibility.GUIDANCE,
            created_by=counselor,
        )
        event.participants.add(head, counselor, advisers[1])
        CalendarEvent.objects.create(
            title="Mental health awareness session (Grade 9)",
            event_type=CalendarEvent.EventType.GUIDANCE_ACTIVITY,
            start=timezone.make_aware(
                datetime.datetime.combine(today + datetime.timedelta(days=5), datetime.time(13, 0))
            ),
            location="AVR",
            visibility=CalendarEvent.Visibility.STAFF,
            created_by=counselor,
        )

        self.stdout.write(self.style.SUCCESS("Demo data loaded."))
        self.stdout.write(f"Sign in with any of these usernames and the password {DEMO_PASSWORD}:")
        for u in [admin, head, counselor, designate, lfo, *advisers]:
            self.stdout.write(
                f"  {u.username:<10} {u.get_role_display()}{' + CPC' if u.is_cpc_member else ''}"
            )
