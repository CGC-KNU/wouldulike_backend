# Generated manually - nickname, student_id, department

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_fix_admin_log_user_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="nickname",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="student_id",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="department",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
