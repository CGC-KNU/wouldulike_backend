"""
파일명 충돌 방지용 no-op migration.
실제 is_active 필드 추가는 0006_admin_account_is_active.py 에서 진행합니다.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0005_admin_account"),
    ]

    operations = []
