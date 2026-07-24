"""
이 migration은 Koyeb 서버에서 자동 생성되어 이미 DB에 적용된 상태입니다.
repo 동기화를 위해 no-op으로 추가합니다.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0003_restaurant_campaign"),
    ]

    operations = []
