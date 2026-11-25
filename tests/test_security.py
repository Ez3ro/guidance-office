"""Encryption, role-based access and the audit trail."""

from cryptography.fernet import Fernet
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.audit.models import AuditEvent, ImmutableAuditError
from apps.core.roles import Cap, Role
from apps.counseling.models import CounselingSession

from .factories import make_section, make_student, make_user


class EncryptionTests(TestCase):
    def test_confidential_fields_are_ciphertext_in_the_database(self):
        counselor = make_user(Role.COUNSELOR)
        session = CounselingSession.objects.create(
            counselor=counselor,
            session_date="2026-11-20",
            primary_concern="wellbeing",
            notes="Learner shared something very private.",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT notes FROM counseling_counselingsession WHERE id = %s", [session.pk]
            )
            stored = cursor.fetchone()[0]
        self.assertTrue(stored.startswith("enc1:"))
        self.assertNotIn("private", stored)
        self.assertEqual(
            CounselingSession.objects.get(pk=session.pk).notes,
            "Learner shared something very private.",
        )

    def test_old_key_still_decrypts_after_rotation(self):
        old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
        counselor = make_user(Role.COUNSELOR)
        with override_settings(FIELD_ENCRYPTION_KEYS=[old]):
            session = CounselingSession.objects.create(
                counselor=counselor,
                session_date="2026-11-20",
                primary_concern="academic",
                notes="secret",
            )
        with override_settings(FIELD_ENCRYPTION_KEYS=[new, old]):
            self.assertEqual(CounselingSession.objects.get(pk=session.pk).notes, "secret")


class RoleTests(TestCase):
    def test_admin_cannot_read_counseling_or_cases(self):
        admin = make_user(Role.ADMIN)
        self.assertTrue(admin.is_staff and admin.is_superuser)
        self.assertFalse(admin.has_cap(Cap.COUNSELING))
        self.assertFalse(admin.has_cap(Cap.VIEW_LRP))
        self.assertTrue(admin.has_cap(Cap.MANAGE_USERS))

    def test_school_head_sees_cases_but_not_session_notes(self):
        head = make_user(Role.SCHOOL_HEAD)
        self.assertTrue(head.has_cap(Cap.VIEW_RESTRICTED_LRP))
        self.assertFalse(head.has_cap(Cap.COUNSELING))
        self.assertFalse(head.is_staff)

    def test_cpc_flag_adds_case_access(self):
        teacher = make_user(Role.TEACHER, is_cpc_member=True)
        self.assertTrue(teacher.has_cap(Cap.VIEW_LRP))
        self.assertFalse(teacher.has_cap(Cap.VIEW_RESTRICTED_LRP))

    def test_inactive_users_have_no_capabilities(self):
        user = make_user(Role.COUNSELOR, is_active=False)
        self.assertEqual(user.capabilities, frozenset())


class AccessTests(TestCase):
    def setUp(self):
        self.counselor = make_user(Role.COUNSELOR)
        self.other_counselor = make_user(Role.COUNSELOR)
        self.teacher = make_user(Role.TEACHER)
        self.head = make_user(Role.SCHOOL_HEAD)
        section = make_section(adviser=self.teacher)
        self.advisee = make_student(section)
        self.other_learner = make_student(make_section())
        self.session = CounselingSession.objects.create(
            counselor=self.counselor, session_date="2026-11-20", primary_concern="family", notes="n"
        )
        self.session.students.add(self.advisee)

    def get(self, user, url):
        self.client.force_login(user)
        return self.client.get(url)

    def test_counseling_is_guidance_only(self):
        url = reverse("counseling:detail", args=[self.session.pk])
        self.assertEqual(self.get(self.counselor, url).status_code, 200)
        self.assertEqual(self.get(self.teacher, url).status_code, 403)
        self.assertEqual(self.get(self.head, url).status_code, 403)

    def test_restricted_session_only_opens_for_its_counselor(self):
        self.session.is_restricted = True
        self.session.save()
        url = reverse("counseling:detail", args=[self.session.pk])
        self.assertEqual(self.get(self.counselor, url).status_code, 200)
        self.assertEqual(self.get(self.other_counselor, url).status_code, 404)

    def test_teacher_sees_only_their_advisory_class(self):
        self.assertEqual(self.get(self.teacher, self.advisee.get_absolute_url()).status_code, 200)
        self.assertEqual(
            self.get(self.teacher, self.other_learner.get_absolute_url()).status_code, 404
        )

    def test_confidential_profile_fields_hidden_from_non_guidance(self):
        self.advisee.health_notes = "Asthma action plan on file"
        self.advisee.save()
        self.assertNotContains(self.get(self.teacher, self.advisee.get_absolute_url()), "Asthma")
        self.assertContains(self.get(self.counselor, self.advisee.get_absolute_url()), "Asthma")

    def test_timeline_hides_counseling_from_school_head(self):
        response = self.get(self.head, self.advisee.get_absolute_url())
        self.assertNotContains(response, "Counseling")

    def test_user_management_is_admin_only(self):
        self.assertEqual(self.get(self.head, reverse("accounts:user_list")).status_code, 403)
        self.assertEqual(
            self.get(make_user(Role.ADMIN), reverse("accounts:user_list")).status_code, 200
        )

    def test_temporary_password_forces_change(self):
        self.teacher.must_change_password = True
        self.teacher.save()
        response = self.get(self.teacher, reverse("core:dashboard"))
        self.assertRedirects(response, reverse("accounts:password_change"))


class AuditTests(TestCase):
    def setUp(self):
        self.counselor = make_user(Role.COUNSELOR)
        self.client.force_login(self.counselor)

    def test_create_update_and_view_are_logged_without_confidential_text(self):
        learner = make_student(make_section())
        response = self.client.post(
            reverse("counseling:create"),
            {
                "students": [learner.pk],
                "counselor": self.counselor.pk,
                "session_date": "2026-11-21",
                "session_type": "individual",
                "modality": "in_person",
                "referral_source": "self",
                "primary_concern": "wellbeing",
                "status": "completed",
                "notes": "VERY-PRIVATE-DETAIL",
            },
        )
        self.assertEqual(
            response.status_code,
            302,
            getattr(response, "context", {}) and response.context["form"].errors,
        )
        session = CounselingSession.objects.get()
        created = AuditEvent.objects.get(
            action="create", model_label="counseling.counselingsession"
        )
        self.assertEqual(created.actor, self.counselor)
        self.assertNotIn("VERY-PRIVATE-DETAIL", str(created.changes))
        self.assertEqual(created.changes["notes"], [None, "(confidential)"])

        self.client.get(session.get_absolute_url())
        self.assertTrue(
            AuditEvent.objects.filter(
                action="view", model_label="counseling.counselingsession", object_id=str(session.pk)
            ).exists()
        )

    def test_audit_events_are_immutable(self):
        event = AuditEvent.objects.create(action="system", object_repr="x")
        event.object_repr = "changed"
        with self.assertRaises(ImmutableAuditError):
            event.save()
        with self.assertRaises(ImmutableAuditError):
            event.delete()
        with self.assertRaises(ImmutableAuditError):
            AuditEvent.objects.all().delete()

    def test_failed_sign_in_is_logged(self):
        self.client.logout()
        self.client.post(
            reverse("accounts:login"), {"username": "nobody", "password": "wrong-password"}
        )
        self.assertTrue(
            AuditEvent.objects.filter(action="login_failed", object_repr="nobody").exists()
        )


@override_settings(AXES_ENABLED=True, AXES_FAILURE_LIMIT=3)
class LockoutTests(TestCase):
    def test_account_locks_after_repeated_failures(self):
        user = make_user(Role.TEACHER, username="locked")
        for _ in range(3):
            self.client.post(reverse("accounts:login"), {"username": "locked", "password": "bad"})
        response = self.client.post(
            reverse("accounts:login"), {"username": "locked", "password": "Correct-Horse-Battery-9"}
        )
        self.assertNotEqual(response.status_code, 302)
        self.assertFalse(
            "_auth_user_id" in self.client.session
            and self.client.session["_auth_user_id"] == str(user.pk)
        )
