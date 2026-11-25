"""Smoke test: every main page renders for the roles that should see it."""

import io

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.counseling.models import CounselingSession
from apps.discipline.models import DisciplinaryCase, ViolationRecord
from apps.interventions.models import InterventionPlan
from apps.protection.models import ProtectionCase
from apps.students.models import Student


@override_settings(DEBUG=True)
class PageSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo_data", force=True, stdout=io.StringIO())

    def urls(self):
        case = ProtectionCase.objects.filter(restricted=False).first()
        violation = ViolationRecord.objects.filter(confiscation="device").first()
        return [
            reverse("core:dashboard"),
            reverse("students:list"),
            reverse("students:detail", args=[Student.objects.first().pk]),
            reverse("discipline:violations"),
            reverse("discipline:violation_detail", args=[violation.pk]),
            reverse("discipline:cases"),
            reverse("discipline:case_detail", args=[DisciplinaryCase.objects.first().pk]),
            reverse("counseling:list"),
            reverse(
                "counseling:detail",
                args=[CounselingSession.objects.filter(is_restricted=False).first().pk],
            ),
            reverse("interventions:list"),
            reverse("interventions:detail", args=[InterventionPlan.objects.first().pk]),
            reverse("protection:list"),
            reverse("protection:detail", args=[case.pk]),
            reverse("protection:create"),
            reverse("scheduling:calendar"),
            reverse("scheduling:followups"),
            reverse("reports:index"),
            reverse("reports:report", args=["lrp_case_summary"]),
            reverse("reports:report", args=["deadline_compliance"]),
            reverse("reports:intake_sheet", args=[case.pk]),
            reverse("reports:confiscation_slip", args=[violation.pk]),
        ]

    def test_counselor_can_open_every_main_page(self):
        self.client.force_login(User.objects.get(username="counselor"))
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_htmx_list_search_returns_partial(self):
        self.client.force_login(User.objects.get(username="counselor"))
        response = self.client.get(reverse("students:list") + "?q=a", HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<nav")
        self.assertContains(response, "<table")

    def test_security_headers(self):
        self.client.force_login(User.objects.get(username="counselor"))
        response = self.client.get(reverse("core:dashboard"))
        self.assertIn("default-src 'self'", response["Content-Security-Policy"])
        self.assertEqual(response["X-Frame-Options"], "DENY")
