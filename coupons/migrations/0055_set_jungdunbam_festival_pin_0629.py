"""우주라이크 X 정든밤(298) PIN을 0629로 고정 (0054 랜덤 PIN 적용분 보정)."""
from __future__ import annotations

from django.db import migrations
from django.utils import timezone


RESTAURANT_ID = 298
MERCHANT_PIN = "0629"


def _apply_pin_on_connection(conn, *, now) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE restaurants_affiliate
            SET pin_secret = %s, pin_updated_at = %s
            WHERE restaurant_id = %s
            """,
            [MERCHANT_PIN, now, RESTAURANT_ID],
        )


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return

    MerchantPin = apps.get_model("coupons", "MerchantPin")
    AffiliateRestaurant = apps.get_model("restaurants", "AffiliateRestaurant")
    now = timezone.now()

    try:
        _apply_pin_on_connection(schema_editor.connection, now=now)
    except Exception:
        pass

    for db_alias in ("cloudsql", "default"):
        try:
            MerchantPin.objects.using(db_alias).update_or_create(
                restaurant_id=RESTAURANT_ID,
                defaults={
                    "algo": "STATIC",
                    "secret": MERCHANT_PIN,
                    "period_sec": 30,
                    "last_rotated_at": now,
                },
            )
            AffiliateRestaurant.objects.using(db_alias).filter(
                restaurant_id=RESTAURANT_ID
            ).update(pin_secret=MERCHANT_PIN, pin_updated_at=now)
        except Exception:
            continue


def backward(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0054_add_jungdunbam_festival_affiliate"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
