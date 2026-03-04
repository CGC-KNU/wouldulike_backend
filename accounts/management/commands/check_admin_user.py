"""
관리자(superuser) 계정 존재 여부 확인 및 로그인 안내.
DB 불일치 시 createsuperuser가 다른 DB에 생성되었을 수 있음.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connections

User = get_user_model()


class Command(BaseCommand):
    help = "관리자(superuser) 계정 확인 및 로그인 안내"

    def handle(self, *args, **options):
        self.stdout.write("\n=== 관리자 계정 확인 ===\n")

        # 현재 사용 중인 DB 확인
        db_alias = "default"
        try:
            with connections[db_alias].cursor() as c:
                c.execute("SELECT 1")
            self.stdout.write(f"DB: {db_alias} (연결됨)")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"DB 연결 실패: {e}"))
            return

        superusers = list(
            User.objects.using(db_alias).filter(is_superuser=True).values("id", "username", "kakao_id")
        )
        if not superusers:
            self.stdout.write(self.style.WARNING("superuser가 없습니다."))
            self.stdout.write(
                "\n다음 명령으로 생성하세요:\n"
                "  python manage.py createsuperuser\n"
                "  Username에 카카오 ID 숫자 입력 (예: 4424486764)\n"
            )
            self.stdout.write(
                "\n⚠️  로그인이 안 되면: createsuperuser 실행 시 DB 설정이 서버와 같은지 확인하세요.\n"
                "  (USE_LOCAL_SQLITE, DISABLE_EXTERNAL_DBS 등)\n"
            )
            return

        self.stdout.write(self.style.SUCCESS(f"superuser {len(superusers)}명 발견:\n"))
        for u in superusers:
            self.stdout.write(f"  - username={u['username']!r}, kakao_id={u['kakao_id']}")

        self.stdout.write(
            "\n--- 로그인 방법 ---\n"
            "  URL: /admin/\n"
            "  Username: 위의 username 값 그대로 입력 (예: 4424486764)\n"
            "  Password: createsuperuser 시 설정한 비밀번호\n"
        )
