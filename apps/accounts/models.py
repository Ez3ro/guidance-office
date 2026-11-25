from __future__ import annotations

from functools import cached_property

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models
from django.urls import reverse

from apps.core.roles import Cap, Role, capabilities_for


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """A staff account. What a user can see is decided by `role` (see core/roles.py)."""

    role = models.CharField(max_length=32, choices=Role.choices, default=Role.TEACHER)
    position = models.CharField(
        max_length=120,
        blank=True,
        help_text="Plantilla position, e.g. Teacher III, Guidance Counselor I",
    )
    is_cpc_member = models.BooleanField(
        "Child Protection Committee member",
        default=False,
        help_text="Gives access to learner rights and protection cases.",
    )
    must_change_password = models.BooleanField(default=False)

    objects = UserManager()

    class Meta:
        ordering = ["last_name", "first_name", "username"]

    def __str__(self) -> str:
        return self.display_name

    def save(self, *args, **kwargs):
        # Only System Administrators may use the Django admin (reference data only).
        is_admin = self.role == Role.ADMIN
        self.is_staff = is_admin
        self.is_superuser = is_admin
        self.__dict__.pop("capabilities", None)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("accounts:user_update", args=[self.pk])

    @property
    def display_name(self) -> str:
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.username

    @cached_property
    def capabilities(self) -> frozenset[Cap]:
        if not self.is_active:
            return frozenset()
        return capabilities_for(self.role, self.is_cpc_member)

    def has_cap(self, *caps: Cap) -> bool:
        """True if the user holds any of the given capabilities."""
        return any(cap in self.capabilities for cap in caps)

    @property
    def is_guidance_staff(self) -> bool:
        return self.has_cap(Cap.COUNSELING)
