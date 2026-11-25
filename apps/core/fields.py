from django.db import models

from .crypto import decrypt_str, encrypt_str


class EncryptedTextField(models.TextField):
    """TextField encrypted at rest.

    The database (and any dump or backup of it) only ever holds ciphertext.
    Encrypted fields can't be searched or filtered on, so keep searchable facts
    (names, dates, categories) in ordinary fields and narratives in these.
    The audit log records that an encrypted field changed, never its contents.
    """

    description = "Text encrypted at rest"

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        return encrypt_str(str(value))

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        return decrypt_str(value)
