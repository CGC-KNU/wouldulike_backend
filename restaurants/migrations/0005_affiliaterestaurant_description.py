from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0004_affiliaterestaurant"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE restaurants_affiliate ADD COLUMN IF NOT EXISTS description TEXT",
                    reverse_sql="ALTER TABLE restaurants_affiliate DROP COLUMN IF EXISTS description",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="affiliaterestaurant",
                    name="description",
                    field=models.TextField(null=True, blank=True),
                ),
            ],
        ),
    ]
