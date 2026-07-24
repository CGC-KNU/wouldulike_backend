"""
파일명 충돌 방지용 no-op migration.
실제 AdminAccount 테이블 생성은 0005_admin_account.py 에서 진행합니다.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0004_alter_adminconfig_options_alter_adminconfig_id_and_more"),
    ]

    operations = []
