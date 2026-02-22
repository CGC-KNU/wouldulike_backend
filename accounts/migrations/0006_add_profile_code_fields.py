from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_add_user_school"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="school_code",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="college_code",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="department_code",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
