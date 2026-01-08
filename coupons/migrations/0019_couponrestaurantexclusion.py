from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0018_update_final_exam_benefit_titles"),
    ]

    operations = [
        migrations.CreateModel(
            name="CouponRestaurantExclusion",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "restaurant_id",
                    models.IntegerField(db_index=True),
                ),
                (
                    "coupon_type",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="excluded_restaurants",
                        to="coupons.coupontype",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("coupon_type", "restaurant_id"),
                        name="uq_coupon_restaurant_exclusion",
                    )
                ],
            },
        ),
    ]


