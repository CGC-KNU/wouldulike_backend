"""슈퍼크리스피(298): s3_image_urls 3장 반영."""

from __future__ import annotations

from django.db import migrations
from django.db.utils import OperationalError, ProgrammingError

RESTAURANT_ID = 298
SUPER_CRISPY_IMAGE_URLS = [
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/supercrispy/supercrispy1.jpeg",
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/supercrispy/supercrispy2.jpeg",
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/supercrispy/supercrispy3.jpeg",
]


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return

    with schema_editor.connection.cursor() as cursor:
        try:
            cursor.execute(
                """
                UPDATE restaurants_affiliate
                SET s3_image_urls = %s
                WHERE restaurant_id = %s
                """,
                [SUPER_CRISPY_IMAGE_URLS, RESTAURANT_ID],
            )
        except (OperationalError, ProgrammingError):
            pass


def backward(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0084_recover_super_crispy_merchant_data"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
