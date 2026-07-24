from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0005_admin_account_is_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="adminaccount",
            name="is_active",
            field=models.BooleanField(default=True, help_text="비활성화 시 로그인 불가"),
        ),
    ]
