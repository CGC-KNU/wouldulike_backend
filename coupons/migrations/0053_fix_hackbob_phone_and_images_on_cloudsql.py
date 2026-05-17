from __future__ import annotations

from django.db import migrations
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone


HACKBOB_NAME_KEYWORD = "핵밥"
HACKBOB_ADDRESS = "대구 북구 대학로 79 2층"
HACKBOB_PHONE_NUMBER = "0507-1337-6783"
HACKBOB_ZONE = "북문"
HACKBOB_CATEGORY = "한식"
HACKBOB_DESCRIPTION = "다양한 덮밥과 라멘 맛집!"
HACKBOB_NAVER_URL = "https://naver.me/G8s2Oz4q"
HACKBOB_PIN = "0306"
HACKBOB_IMAGE_URLS = [
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/hackbob/hackbob1.jpeg",
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/hackbob/hackbob2.jpeg",
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/hackbob/hackbob3.jpeg",
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/hackbob/hackbob4.jpeg",
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/hackbob/hackbob5.jpeg",
]


def _pick_hackbob_restaurant_id_via_sql(conn) -> int | None:
    """
    마이그레이션 히스토리 모델에는 필드가 없을 수 있어 ORM을 쓰면 FieldDoesNotExist가 날 수 있음.
    cloudsql 연결에서 raw SQL로 restaurant_id를 찾는다.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT restaurant_id, COALESCE(address, '') AS address
            FROM restaurants_affiliate
            WHERE name ILIKE %s
            LIMIT 20
            """,
            [f"%{HACKBOB_NAME_KEYWORD}%"],
        )
        rows = cursor.fetchall() or []
    if not rows:
        return None
    for rid, addr in rows:
        if addr and HACKBOB_ADDRESS in addr:
            return int(rid)
    return int(rows[0][0])


def forward(apps, schema_editor):
    """
    0052에서 default DB로 update()가 0건이어도 예외가 안 나서 cloudsql 업데이트가 스킵될 수 있음.
    따라서 cloudsql에 핵밥의 사진/전화번호/설명/핀 등을 강제로 재반영한다.
    """
    if schema_editor.connection.vendor == "sqlite":
        return

    MerchantPin = apps.get_model("coupons", "MerchantPin")

    conn = schema_editor.connection
    restaurant_id = _pick_hackbob_restaurant_id_via_sql(conn)
    if not restaurant_id:
        return

    now = timezone.now()
    # NOTE: apps.get_model(...)로 얻은 히스토리 모델에는 필드가 없을 수 있어 ORM update()를 쓰지 않는다.
    # 컬럼 유무가 환경별로 다를 수 있으니 raw SQL을 "시도 후 실패 시 스킵" 방식으로 적용한다.
    with conn.cursor() as cursor:
        # 기본 텍스트 컬럼들(없으면 예외 → 스킵)
        try:
            cursor.execute(
                """
                UPDATE restaurants_affiliate
                SET
                  address = %s,
                  phone_number = %s,
                  zone = %s,
                  category = %s,
                  url = %s,
                  description = %s,
                  pin_secret = %s,
                  pin_updated_at = %s
                WHERE restaurant_id = %s
                """,
                [
                    HACKBOB_ADDRESS,
                    HACKBOB_PHONE_NUMBER,
                    HACKBOB_ZONE,
                    HACKBOB_CATEGORY,
                    HACKBOB_NAVER_URL,
                    HACKBOB_DESCRIPTION,
                    HACKBOB_PIN,
                    now,
                    restaurant_id,
                ],
            )
        except (OperationalError, ProgrammingError):
            pass

        # is_affiliate 컬럼이 있을 때만 반영
        try:
            cursor.execute(
                "UPDATE restaurants_affiliate SET is_affiliate = TRUE WHERE restaurant_id = %s",
                [restaurant_id],
            )
        except (OperationalError, ProgrammingError):
            pass

        # s3_image_urls 컬럼이 있을 때만 반영 (Postgres array)
        try:
            cursor.execute(
                "UPDATE restaurants_affiliate SET s3_image_urls = %s WHERE restaurant_id = %s",
                [HACKBOB_IMAGE_URLS, restaurant_id],
            )
        except (OperationalError, ProgrammingError):
            pass

    # PIN 테이블도 cloudsql에 맞춰 재반영 (운영에서 coupons도 cloudsql을 쓸 수 있음)
    try:
        MerchantPin.objects.using("cloudsql").update_or_create(
            restaurant_id=restaurant_id,
            defaults={
                "algo": "STATIC",
                "secret": HACKBOB_PIN,
                "period_sec": 30,
                "last_rotated_at": now,
            },
        )
    except Exception:
        # cloudsql에 coupons 테이블이 없는 환경일 수 있어 안전 스킵
        pass


def backward(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0052_add_hackbob_affiliate_and_rewards"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]

