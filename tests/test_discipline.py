import datetime

from django.test import TestCase
from django.urls import reverse

from apps.core.roles import Role
from apps.discipline.models import DisciplinaryCase, ViolationRecord
from apps.scheduling.models import FollowUp

from .factories import make_section, make_student, make_user, offense


class DueProcessTests(TestCase):
    def setUp(self):
        self.lfo = make_user(Role.LFO)
        self.learner = make_student(make_section())

    def make_case(self, **extra):
        case = DisciplinaryCase.objects.create(
            title="Test", summary="Facts", handled_by=self.lfo, **extra
        )
        case.respondents.add(self.learner)
        return case

    def test_notice_creates_10_day_answer_follow_up(self):
        case = self.make_case(notice_served_on=datetime.date(2026, 11, 3))
        fu = FollowUp.objects.get(object_id=case.pk, rule_key="discipline.answer_due")
        self.assertEqual(case.answer_due, datetime.date(2026, 11, 13))
        self.assertEqual(fu.assigned_to, self.lfo)
        case.answer_received_on = datetime.date(2026, 11, 10)
        case.save()
        fu.refresh_from_db()
        self.assertEqual(fu.status, FollowUp.Status.DONE)

    def test_appeal_period_is_15_days_or_10_for_bullying(self):
        normal = self.make_case(decision_date=datetime.date(2026, 11, 1), decision="Decision")
        bullying = self.make_case(
            decision_date=datetime.date(2026, 11, 1), decision="Decision", is_bullying=True
        )
        self.assertEqual(normal.appeal_deadline, datetime.date(2026, 11, 16))
        self.assertEqual(bullying.appeal_deadline, datetime.date(2026, 11, 11))
        self.assertIn("Legal and Legislative Affairs", bullying.appeal_body)
        self.assertTrue(
            FollowUp.objects.filter(
                object_id=bullying.pk, rule_key="discipline.appeal_period"
            ).exists()
        )

    def test_case_numbers_are_sequential(self):
        first, second = self.make_case(), self.make_case()
        self.assertEqual(int(second.case_number[-4:]), int(first.case_number[-4:]) + 1)


class ViolationTests(TestCase):
    def setUp(self):
        self.teacher = make_user(Role.TEACHER)
        self.learner = make_student(make_section(adviser=self.teacher))
        self.device = offense("L1-05", 1, is_device_related=True)

    def test_offence_count_drives_progressive_sanctions(self):
        records = [
            ViolationRecord.objects.create(
                student=self.learner,
                offense_type=self.device,
                incident_date=datetime.date.today() - datetime.timedelta(days=d),
                description="Phone out in class",
            )
            for d in (20, 10, 1)
        ]
        self.assertEqual([r.offense_count for r in records], [1, 2, 3])
        self.assertEqual(records[2].offense_ordinal, "3rd offence")

    def test_teacher_can_log_a_violation_and_edit_it_while_open(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("discipline:violation_create"),
            {
                "student": self.learner.pk,
                "offense_type": self.device.pk,
                "incident_date": "2026-11-20",
                "description": "Phone out during the quiz.",
                "confiscation": "device",
                "confiscated_item": "Mobile phone",
            },
        )
        self.assertEqual(
            response.status_code, 302, response.context and response.context["form"].errors
        )
        violation = ViolationRecord.objects.get()
        self.assertEqual(violation.reported_by, self.teacher)
        self.assertTrue(violation.user_can_edit(self.teacher))
        slip = self.client.get(reverse("reports:confiscation_slip", args=[violation.pk]))
        self.assertContains(slip, "Annex J")
        violation.status = ViolationRecord.Status.RESOLVED
        violation.save()
        self.assertFalse(violation.user_can_edit(self.teacher))
