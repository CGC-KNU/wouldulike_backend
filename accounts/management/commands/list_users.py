from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class Command(BaseCommand):
    help = '사용자 목록을 조회하여 카카오 ID를 확인합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--kakao-only',
            action='store_true',
            help='카카오 로그인 사용자만 조회',
        )
        parser.add_argument(
            '--search',
            type=str,
            help='카카오 ID로 검색 (부분 일치)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='출력할 최대 사용자 수 (기본값: 50)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='모든 사용자 출력 (--limit 무시)',
        )

    def handle(self, *args, **options):
        search_term = options.get('search')
        limit = options.get('limit')
        show_all = options.get('all')
        kakao_only = options.get('kakao_only')

        # 쿼리 구성
        if kakao_only:
            users = User.objects.exclude(kakao_id__isnull=True)
        else:
            users = User.objects.all()
        
        if search_term:
            try:
                # 숫자로 검색 시도
                search_id = int(search_term)
                users = users.filter(kakao_id__icontains=search_id)
            except ValueError:
                # 문자열 검색
                users = users.filter(kakao_id__icontains=search_term)

        # 정렬: 최근 생성된 순서
        users = users.order_by('-created_at')

        # 제한
        if not show_all:
            users = users[:limit]
            total_count = User.objects.count()
        else:
            total_count = users.count()

        # 결과 출력
        title = '카카오 로그인 사용자 목록' if kakao_only else '사용자 목록'
        self.stdout.write(self.style.SUCCESS(f'\n=== {title} (총 {total_count}명) ===\n'))
        
        if not users.exists():
            self.stdout.write(self.style.WARNING('검색 결과가 없습니다.'))
            return

        # 헤더
        self.stdout.write(f"{'ID':<8} {'카카오 ID':<15} {'타입':<6} {'생성일':<20} {'활성':<6}")
        self.stdout.write('-' * 70)

        for user in users:
            active_status = '✓' if user.is_active else '✗'
            type_code = user.type_code or '-'
            created_at = user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else '-'
            
            self.stdout.write(
                f"{user.id:<8} {user.kakao_id:<15} {type_code:<6} {created_at:<20} {active_status:<6}"
            )

        if not show_all and total_count > limit:
            self.stdout.write(f'\n... 외 {total_count - limit}명 더 있습니다. --all 옵션으로 전체를 볼 수 있습니다.')

        self.stdout.write('')

