from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('kakao_id', models.BigIntegerField(db_index=True, unique=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('nickname', models.CharField(blank=True, max_length=255, null=True)),
                ('profile_image_url', models.URLField(blank=True, null=True)),
                ('type_code', models.CharField(blank=True, max_length=4, null=True)),
                ('favorite_restaurants', models.TextField(blank=True, null=True)),
                ('fcm_token', models.CharField(blank=True, max_length=255, null=True)),
                ('preferences', models.JSONField(blank=True, null=True)),
                ('survey_responses', models.JSONField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('is_staff', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_superuser', models.BooleanField(default=False)),
                (
                    'groups',
                    models.ManyToManyField(
                        blank=True,
                        related_name='user_set',
                        related_query_name='user',
                        to='auth.group',
                    ),
                ),
                (
                    'user_permissions',
                    models.ManyToManyField(
                        blank=True,
                        related_name='user_set',
                        related_query_name='user',
                        to='auth.permission',
                    ),
                ),
            ],
        ),
    ]