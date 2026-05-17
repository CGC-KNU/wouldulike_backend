"""
0064/0065 가 default DB 에만 반영되고 앱은 cloudsql 에서 coupons 를 읽는 경우를 보정.
"""
from django.db import migrations


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return

    from coupons.pub_jujeom_event import ensure_pub_jujeom_event_data, resolve_cloudsql_alias

    ensure_pub_jujeom_event_data(db_alias=resolve_cloudsql_alias())


def backward(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0065_expand_pub_jujeom_event_targets"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
