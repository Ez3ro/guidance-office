"""Makes the audit table append-only at the database level on PostgreSQL.

Django already refuses to update or delete AuditEvent rows; this trigger also stops
UPDATE and DELETE issued directly in SQL (for example from the Supabase SQL editor
by mistake). It is skipped on SQLite, which is used for local development and tests.
"""

from django.db import migrations

CREATE = """
CREATE OR REPLACE FUNCTION audit_auditevent_block_changes() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_auditevent is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_auditevent_append_only ON audit_auditevent;
CREATE TRIGGER audit_auditevent_append_only
    BEFORE UPDATE OR DELETE ON audit_auditevent
    FOR EACH ROW EXECUTE FUNCTION audit_auditevent_block_changes();
"""

DROP = """
DROP TRIGGER IF EXISTS audit_auditevent_append_only ON audit_auditevent;
DROP FUNCTION IF EXISTS audit_auditevent_block_changes();
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CREATE)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(DROP)


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]

    operations = [migrations.RunPython(forwards, backwards)]
