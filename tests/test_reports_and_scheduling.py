import datetime
from io import BytesIO

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from apps.core.roles import Role
from apps.protection.models import CaseParty
from apps.reports.services import Period, annual_bullying_report
from apps.scheduling.models import FollowUp

from .factories import concern, make_case, make_section, make_student, make_user


class ReportTests(TestCase):
    def setUp(self):
        self.counselor = make_user(Role.COUNSELOR)
        section = make_section(grade="8")
        for sex in ("F", "M", "F"):
            case = make_case(received_by=self.counselor)
            case.concern_types.set([concern("Cyberbullying")])
            CaseParty.objects.create(
                case=case,
                role=CaseParty.Role.VICTIM,
                student=make_student(
                    section, sex=sex, first_name="Zebedee", last_name="Quillfeather"
                ),
            )
        self.period = Period(
            timezone.localdate() - datetime.timedelta(days=30), timezone.localdate(), "test"
        )

    def test_annual_bullying_report_counts_by_sex_and_grade(self):
        report = annual_bullying_report(self.period)
        by_type = report.tables[0].rows
        self.assertEqual(by_type[0], ["Cyberbullying", 1, 2, 0, 3])
        by_grade = report.tables[1].rows
        self.assertEqual(by_grade[0], ["Grade 8", 1, 2, 0, 3])

    def test_reports_never_include_learner_names(self):
        self.client.force_login(self.counselor)
        response = self.client.get(reverse("reports:report", args=["lrp_case_summary"]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Zebedee")
        self.assertNotContains(response, "Quillfeather")

    def test_excel_export_is_a_valid_workbook_and_is_logged(self):
        self.client.force_login(self.counselor)
        response = self.client.get(
            reverse("reports:report", args=["annual_bullying"]) + "?format=xlsx"
        )
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.content))
        self.assertIn("Report", workbook.sheetnames)
        self.assertGreater(len(workbook.sheetnames), 3)
        from apps.audit.models import AuditEvent

        self.assertTrue(AuditEvent.objects.filter(action="export").exists())

    def test_teachers_cannot_open_reports(self):
        self.client.force_login(make_user(Role.TEACHER))
        self.assertEqual(self.client.get(reverse("reports:index")).status_code, 403)


class CronTests(TestCase):
    @override_settings(CRON_SECRET="s3cret")
    def test_cron_requires_the_bearer_secret(self):
        url = reverse("core:cron_daily")
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.get(url, HTTP_AUTHORIZATION="Bearer wrong").status_code, 401)
        self.assertEqual(self.client.get(url, HTTP_AUTHORIZATION="Bearer s3cret").status_code, 200)

    @override_settings(CRON_SECRET="")
    def test_cron_is_disabled_without_a_secret(self):
        self.assertEqual(self.client.get(reverse("core:cron_daily")).status_code, 401)

    @override_settings(CRON_SECRET="s3cret")
    def test_digest_emails_titles_only(self):
        counselor = make_user(Role.COUNSELOR)
        case = make_case(
            received_by=counselor, reported_at=timezone.now() - datetime.timedelta(days=3)
        )
        response = self.client.get(reverse("core:cron_daily"), HTTP_AUTHORIZATION="Bearer s3cret")
        self.assertEqual(response.json()["users_emailed"], 1)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn(case.case_number, body)
        self.assertIn("OVERDUE", body)
        self.assertNotIn(case.narrative, body)

    def test_follow_up_done_via_htmx(self):
        user = make_user(Role.COUNSELOR)
        fu = FollowUp.objects.create(title="Call parent", due_at=timezone.now(), assigned_to=user)
        self.client.force_login(user)
        response = self.client.post(
            reverse("scheduling:followup_done", args=[fu.pk]), HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        fu.refresh_from_db()
        self.assertEqual(fu.status, FollowUp.Status.DONE)
        self.assertEqual(fu.completed_by, user)
