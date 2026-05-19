"""술집·주점 대상 식당 전원에 PUB_JUJEOM_EVENT benefit 이 있도록 보강 (YUNJI 5종 대비)."""
from django.db import migrations


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return

    from coupons.festival_jungdunbam import resolve_cloudsql_alias
    from coupons.pub_jujeom_event import ensure_pub_jujeom_event_data

    ensure_pub_jujeom_event_data(db_alias=resolve_cloudsql_alias())


def backward(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0075_ensure_child_dept_cloudsql_raw_sql"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
