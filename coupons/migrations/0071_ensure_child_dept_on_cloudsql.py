"""CHILD_DEPT_COUPON_PACK 을 CloudSQL(앱 조회 DB)에 반영."""
from django.db import migrations


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return

    from coupons.child_dept_event import ensure_child_dept_event_data
    from coupons.festival_jungdunbam import resolve_cloudsql_alias

    ensure_child_dept_event_data(db_alias=resolve_cloudsql_alias())


def backward(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0070_add_child_dept_coupon_pack"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
