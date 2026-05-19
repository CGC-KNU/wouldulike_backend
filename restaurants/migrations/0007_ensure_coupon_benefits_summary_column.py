"""cloudsql 등 실제 restaurants_affiliate 가 있는 DB에 컬럼이 없을 때 보정."""

from django.db import migrations

from restaurants.migrations._affiliate_column_ops import (
    add_coupon_benefits_summary_column_if_table_exists,
    remove_coupon_benefits_summary_column_if_table_exists,
)


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0006_affiliaterestaurant_coupon_benefits_summary"),
    ]

    operations = [
        migrations.RunPython(
            add_coupon_benefits_summary_column_if_table_exists,
            remove_coupon_benefits_summary_column_if_table_exists,
        ),
    ]
