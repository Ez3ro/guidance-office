"""DO 006, s. 2026 workflow for learner rights and protection cases."""

import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.roles import Role
from apps.protection.models import CaseParty, ConcernCategory, ProtectionCase, RiskAssessment
from apps.scheduling.models import FollowUp

from .factories import concern, make_case, make_section, make_student, make_user


def follow_up(case, rule):
    return FollowUp.objects.get(object_id=case.pk, rule_key=rule)


class DeadlineTests(TestCase):
    def setUp(self):
        self.counselor = make_user(Role.COUNSELOR)

    def test_new_case_gets_risk_assessment_and_48_hour_intake_follow_ups(self):
        reported = timezone.now()
        case = make_case(received_by=self.counselor, reported_at=reported)
        self.assertTrue(case.case_number.startswith(f"CP-{timezone.localdate().year}-"))
        intake = follow_up(case, "lrp.intake_48h")
        self.assertEqual(intake.due_at, reported + datetime.timedelta(hours=48))
        self.assertEqual(intake.assigned_to, self.counselor)
        self.assertEqual(intake.module, FollowUp.Module.LRP)
        self.assertEqual(follow_up(case, "lrp.risk_assessment").status, FollowUp.Status.OPEN)

    def test_risk_assessment_closes_its_follow_up_and_advances_status(self):
        case = make_case(received_by=self.counselor)
        RiskAssessment.objects.create(
            case=case,
            risk_factors="x",
            actions_needed="y",
            responsible_persons="RGC",
            timeline="today",
            parents_notified=True,
        )
        case.refresh_from_db()
        self.assertEqual(case.status, ProtectionCase.Status.ASSESSED)
        self.assertEqual(follow_up(case, "lrp.risk_assessment").status, FollowUp.Status.DONE)

    def test_milestones_close_follow_ups_and_create_the_10_and_30_day_deadlines(self):
        reported = timezone.make_aware(datetime.datetime(2026, 11, 2, 9, 0))
        case = make_case(received_by=self.counselor, reported_at=reported)
        case.intake_referred_at = reported + datetime.timedelta(hours=20)
        case.fact_finding_started_on = datetime.date(2026, 11, 4)
        case.save()
        case.refresh_from_db()
        self.assertEqual(case.status, ProtectionCase.Status.FACT_FINDING)
        self.assertEqual(follow_up(case, "lrp.intake_48h").status, FollowUp.Status.DONE)
        findings = follow_up(case, "lrp.findings_10d")
        self.assertEqual(timezone.localtime(findings.due_at).date(), datetime.date(2026, 11, 14))
        forward = follow_up(case, "lrp.forward_30d")
        self.assertEqual(timezone.localtime(forward.due_at).date(), datetime.date(2026, 12, 2))

        states = {d.label: d.state for d in case.deadlines()}
        self.assertEqual(
            states["Incident Report and Intake Sheet to disciplining authority"], "met"
        )

    def test_late_intake_is_reported_as_missed(self):
        reported = timezone.now() - datetime.timedelta(days=5)
        case = make_case(received_by=self.counselor, reported_at=reported)
        case.intake_referred_at = reported + datetime.timedelta(hours=60)
        case.save()
        states = {d.label: d.state for d in case.deadlines()}
        self.assertEqual(
            states["Incident Report and Intake Sheet to disciplining authority"], "missed"
        )

    def test_closing_a_case_cancels_open_follow_ups(self):
        case = make_case(received_by=self.counselor)
        case.status = ProtectionCase.Status.DISMISSED
        case.save()
        self.assertFalse(
            FollowUp.objects.filter(object_id=case.pk, status=FollowUp.Status.OPEN).exists()
        )
        self.assertIsNotNone(case.closed_on)


class ConfidentialityTests(TestCase):
    def setUp(self):
        self.counselor = make_user(Role.COUNSELOR)
        self.lfo = make_user(Role.LFO)
        self.head = make_user(Role.SCHOOL_HEAD)
        self.teacher = make_user(Role.TEACHER)

    def test_sensitive_concern_restricts_the_case_and_its_follow_ups(self):
        learner = make_student(make_section(adviser=self.teacher))
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("protection:report"),
            {
                "learners": [learner.pk],
                "concern_types": [
                    concern("Sexual abuse", ConcernCategory.CHILD_ABUSE, sensitive=True).pk
                ],
                "incident_location": "on_campus",
                "narrative": "Learner disclosed something to me after class.",
            },
        )
        self.assertEqual(response.status_code, 200)
        case = ProtectionCase.objects.get()
        self.assertTrue(case.restricted)
        self.assertEqual(case.created_by, self.teacher)
        self.assertTrue(case.parties.filter(role=CaseParty.Role.VICTIM, student=learner).exists())
        self.assertTrue(FollowUp.objects.filter(object_id=case.pk, restricted=True).exists())

        url = case.get_absolute_url()
        self.client.force_login(self.lfo)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertFalse(FollowUp.objects.visible_to(self.lfo).filter(object_id=case.pk).exists())
        self.client.force_login(self.head)
        self.assertContains(self.client.get(url), "Learner disclosed")

    def test_reporter_sees_status_but_not_details(self):
        self.client.force_login(self.teacher)
        self.client.post(
            reverse("protection:report"),
            {
                "concern_types": [concern().pk],
                "incident_location": "online",
                "narrative": "Group chat messages DETAIL-XYZ.",
            },
        )
        case = ProtectionCase.objects.get()
        response = self.client.get(case.get_absolute_url())
        self.assertContains(response, case.case_number)
        self.assertNotContains(response, "DETAIL-XYZ")
        self.assertEqual(self.client.get(reverse("protection:list")).status_code, 403)

    def test_staff_create_case_with_parties(self):
        victim = make_student(make_section())
        respondent = make_student(make_section(), sex="M")
        self.client.force_login(self.counselor)
        response = self.client.post(
            reverse("protection:create"),
            {
                "reported_at": "2026-11-24T08:30",
                "received_by": self.counselor.pk,
                "report_channel": "disclosure",
                "incident_location": "on_campus",
                "narrative": "Reported by the learner during homeroom.",
                "victims": [victim.pk],
                "learner_respondents": [respondent.pk],
                "concern_types": [concern().pk],
                "flow": "B",
                "status": "reported",
            },
        )
        self.assertEqual(
            response.status_code, 302, response.context and response.context["form"].errors
        )
        case = ProtectionCase.objects.get()
        self.assertEqual(case.victims.get().student, victim)
        self.assertEqual(case.respondents.get().student, respondent)
        self.assertFalse(case.restricted)
