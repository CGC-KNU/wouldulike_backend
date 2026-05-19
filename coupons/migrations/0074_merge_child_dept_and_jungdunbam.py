"""0070 분기(아동학부 쿠폰팩 / 정든밤 축제) 병합."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0071_ensure_child_dept_on_cloudsql"),
        ("coupons", "0072_jungdunbam_festival_restaurant_id_299"),
    ]

    operations = []
