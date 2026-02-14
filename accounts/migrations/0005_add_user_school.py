# Generated manually - school (학교 정보)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_add_user_profile_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="school",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
