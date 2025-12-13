from django.db import migrations, models, connection


def add_description_column_if_table_exists(apps, schema_editor):
    """테이블이 존재하는 경우에만 description 컬럼을 추가합니다."""
    with connection.cursor() as cursor:
        # 테이블 존재 여부 확인
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'restaurants_affiliate'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            # 테이블이 존재하면 컬럼 추가
            cursor.execute("""
                ALTER TABLE restaurants_affiliate 
                ADD COLUMN IF NOT EXISTS description TEXT;
            """)
        # 테이블이 없으면 아무것도 하지 않음 (CloudSQL에만 존재할 수 있음)


def remove_description_column_if_table_exists(apps, schema_editor):
    """테이블이 존재하는 경우에만 description 컬럼을 제거합니다."""
    with connection.cursor() as cursor:
        # 테이블 존재 여부 확인
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'restaurants_affiliate'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            # 테이블이 존재하면 컬럼 제거
            cursor.execute("""
                ALTER TABLE restaurants_affiliate 
                DROP COLUMN IF EXISTS description;
            """)


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0004_affiliaterestaurant"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_description_column_if_table_exists,
                    remove_description_column_if_table_exists,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="affiliaterestaurant",
                    name="description",
                    field=models.TextField(null=True, blank=True),
                ),
            ],
        ),
    ]
