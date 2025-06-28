from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001__init__'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='sent',
            field=models.BooleanField(default=False),
        ),
    ]