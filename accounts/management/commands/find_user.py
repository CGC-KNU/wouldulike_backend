"""
사용자 검색 명령어. 우주라이크 ID, apple_id, user id, 카카오 ID로 검색 가능.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class Command(BaseCommand):
    help = '우주라이크 ID, Apple ID, user id, 카카오 ID로 사용자를 검색합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            'search',
            type=str,
            nargs='?',
            help='검색어 (우주라이크 ID, apple_id, user id, 카카오 ID)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='출력할 최대 사용자 수 (기본값: 20)',
        )

    def handle(self, *args, **options):
        search = options.get('search')
        limit = options['limit']

        if search:
            # 검색어로 사용자 찾기
            users = self._find_users(search, limit)
        else:
            # 검색어 없으면 Apple 사용자 최근 N명 출력
            users = User.objects.filter(apple_id__isnull=False).order_by('-created_at')[:limit]

        if not users:
            self.stdout.write(self.style.WARNING('검색 결과가 없습니다.'))
            if search:
                self.stdout.write('')
                self.stdout.write('다음 방법을 시도해보세요:')
                self.stdout.write('  1. 우주라이크 ID 전체: python manage.py find_user "001528.90360a381f054339a3aec5d3de29608d.1919"')
                self.stdout.write('  2. user id만: python manage.py find_user 1528')
                self.stdout.write('  3. apple_id 부분: python manage.py find_user 90360a38')
                self.stdout.write('')
                self.stdout.write('현재 DB에 연결된 환경을 확인하세요 (로컬 vs 운영).')
            return

        self.stdout.write(self.style.SUCCESS(f'\n=== 검색 결과 (총 {len(users)}명) ===\n'))
        self.stdout.write(f"{'ID':<8} {'Apple ID':<40} {'카카오 ID':<15} {'생성일':<20}")
        self.stdout.write('-' * 90)

        for user in users:
            apple_id = (user.apple_id or '-')[:38]
            kakao_id = str(user.kakao_id) if user.kakao_id else '-'
            created = user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else '-'
            self.stdout.write(f"{user.id:<8} {apple_id:<40} {kakao_id:<15} {created:<20}")

        self.stdout.write('')
        self.stdout.write('삭제 명령어 예시:')
        self.stdout.write(f'  python manage.py delete_user_data --user-id <ID>')
        self.stdout.write(f'  python manage.py delete_user_data --apple-id <Apple ID>')
        self.stdout.write('')

    def _find_users(self, search: str, limit: int):
        """여러 방식으로 사용자 검색"""
        search = search.strip()
        if not search:
            return User.objects.none()

        # 1) 숫자만 있으면 user id 또는 카카오 ID로 검색
        try:
            num = int(search)
            users = User.objects.filter(Q(id=num) | Q(kakao_id=num))[:limit]
            if users:
                return list(users)
        except ValueError:
            pass

        # 2) 우주라이크 ID 형식 (001528.xxx.yyy) - 앞부분이 user id일 수 있음
        if '.' in search:
            parts = search.split('.')
            if parts[0].isdigit():
                try:
                    uid = int(parts[0])
                    user = User.objects.filter(id=uid).first()
                    if user:
                        return [user]
                except ValueError:
                    pass

        # 3) apple_id 정확히 일치
        user = User.objects.filter(apple_id=search).first()
        if user:
            return [user]

        # 4) apple_id 부분 일치 (contains)
        users = User.objects.filter(apple_id__icontains=search).order_by('-created_at')[:limit]
        if users:
            return list(users)

        # 5) username 일치 (apple_xxx 형식)
        users = User.objects.filter(username__icontains=search).order_by('-created_at')[:limit]
        if users:
            return list(users)

        return User.objects.none()
