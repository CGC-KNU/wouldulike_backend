from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('guests', '0003_remove_guestuser_favorite_restaurants_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='guestuser',
            name='fcm_token',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
    ]