"""CloudSQL: 0070 실패 복구 — 아동학부 쿠폰팩 raw SQL 경로로 재반영."""

from django.db import migrations


def apply(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return

    from coupons.child_dept_event import ensure_child_dept_event_data
    from coupons.festival_jungdunbam import resolve_cloudsql_alias

    ensure_child_dept_event_data(db_alias=resolve_cloudsql_alias())


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0073_fix_jungdunbam_id_reassign_conflicts"),
    ]

    operations = [
        migrations.RunPython(apply, migrations.RunPython.noop),
    ]
