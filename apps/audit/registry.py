"""Which models get automatic change logging.

Each app registers its models in AppConfig.ready() or at the bottom of models.py:

    from apps.audit.registry import register
    register(Student, Enrollment)
"""

from __future__ import annotations

AUDITED_MODELS: set[type] = set()

# Bookkeeping fields that add noise to change logs.
IGNORED_FIELDS = {"created_at", "updated_at", "created_by", "updated_by", "password", "last_login"}


def register(*models: type) -> None:
    AUDITED_MODELS.update(models)


def is_audited(model: type) -> bool:
    return model in AUDITED_MODELS
