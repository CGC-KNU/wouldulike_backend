# Generated by Django 4.2.6 on 2025-01-12 09:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trends', '0002_alter_trend_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='trend',
            name='image',
            field=models.ImageField(upload_to='trend_images/'),
        ),
    ]
