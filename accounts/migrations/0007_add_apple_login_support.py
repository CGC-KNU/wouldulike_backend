# Generated manually for Apple Sign In support

from django.db import migrations, models


def cleanup_and_add_username_raw(apps, schema_editor):
    """
    AddField 대신 raw SQL로 username 처리. 인덱스 충돌 회피.
    """
    from django.db import connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        # 1. 기존 username 관련 인덱스/컬럼 제거
        cursor.execute("""
            SELECT schemaname, indexname FROM pg_indexes
            WHERE tablename = 'accounts_user' AND indexname LIKE '%username%';
        """)
        for schemaname, indexname in cursor.fetchall():
            cursor.execute(f'DROP INDEX IF EXISTS "{schemaname}"."{indexname}";')
        cursor.execute("ALTER TABLE accounts_user DROP COLUMN IF EXISTS username;")
        # 2. 컬럼 추가 (nullable, 인덱스 없이 - 나중에 AlterField에서 추가)
        cursor.execute("""
            ALTER TABLE accounts_user
            ADD COLUMN username VARCHAR(255) NULL;
        """)


def reverse_cleanup_and_add_username(apps, schema_editor):
    """rollback 시 username 컬럼 제거"""
    from django.db import connection
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT schemaname, indexname FROM pg_indexes
                WHERE tablename = 'accounts_user' AND indexname LIKE '%username%';
            """)
            for schemaname, indexname in cursor.fetchall():
                cursor.execute(f'DROP INDEX IF EXISTS "{schemaname}"."{indexname}";')
            cursor.execute("ALTER TABLE accounts_user DROP COLUMN IF EXISTS username;")


def backfill_username(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.all():
        if user.kakao_id is not None:
            user.username = str(user.kakao_id)
            user.save(update_fields=["username"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_add_profile_code_fields"),
    ]

    operations = [
        # 1. username 컬럼 추가 (raw SQL로 인덱스 충돌 회피)
        migrations.RunPython(cleanup_and_add_username_raw, reverse_cleanup_and_add_username),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="user",
                    name="username",
                    field=models.CharField(db_index=True, max_length=255, null=True, unique=False),
                ),
            ],
        ),
        # 2. Add apple_id
        migrations.AddField(
            model_name="user",
            name="apple_id",
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True, unique=True),
        ),
        # 2b. Add email (for Apple users)
        migrations.AddField(
            model_name="user",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        # 3. Backfill username for existing users
        migrations.RunPython(backfill_username, migrations.RunPython.noop),
        # 4. Make username non-null and unique
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(db_index=True, max_length=255, unique=True),
        ),
        # 5. Make kakao_id nullable
        migrations.AlterField(
            model_name="user",
            name="kakao_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True, unique=True),
        ),
        # 6. Create SocialAccount model
        migrations.CreateModel(
            name="SocialAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("apple", "Apple")], max_length=32)),
                ("provider_user_id", models.CharField(db_index=True, max_length=255)),
                ("email", models.EmailField(blank=True, max_length=254, null=True)),
                ("user", models.ForeignKey(on_delete=models.CASCADE, related_name="social_accounts", to="accounts.user")),
            ],
            options={
                "unique_together": {("provider", "provider_user_id")},
            },
        ),
    ]
