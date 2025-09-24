from django.db import migrations


def fix_admin_log_user_fk(apps, schema_editor):
    connection = schema_editor.connection

    # PostgreSQL에서만 FK를 직접 수정한다.
    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                tc.constraint_name,
                ccu.table_name AS referenced_table
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = 'django_admin_log'
              AND ccu.column_name = 'id'
              AND ccu.table_name IN ('auth_user', 'accounts_user')
            ORDER BY ccu.table_name = 'auth_user' DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()

        if not row:
            return

        constraint_name, referenced_table = row

        # 이미 accounts_user를 바라보도록 구성되어 있다면 추가 작업 불필요
        if referenced_table == "accounts_user":
            return

        log_table = schema_editor.quote_name("django_admin_log")
        accounts_table = schema_editor.quote_name("accounts_user")
        constraint = schema_editor.quote_name(constraint_name)

        # FK를 교체하기 전에 유효하지 않은 레코드를 정리한다.
        cursor.execute(
            f"""
            DELETE FROM {log_table}
            WHERE user_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM {accounts_table}
                  WHERE {accounts_table}.id = {log_table}.user_id
              )
            """
        )

        cursor.execute(
            f"ALTER TABLE {log_table} DROP CONSTRAINT {constraint}"
        )
        cursor.execute(
            f"""
            ALTER TABLE {log_table}
            ADD CONSTRAINT {constraint}
            FOREIGN KEY (user_id)
            REFERENCES {accounts_table}(id)
            ON DELETE CASCADE
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_remove_user_email_remove_user_nickname_and_more"),
        ("admin", "0003_logentry_add_action_flag_choices"),
    ]

    operations = [
        migrations.RunPython(fix_admin_log_user_fk, migrations.RunPython.noop),
    ]
