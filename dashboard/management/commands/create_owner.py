"""
Usage:
  python manage.py create_owner --kakao_id 4424485674 --restaurant_id <id>
  python manage.py create_owner --kakao_id 4424485674  # 첫 번째 레스토랑 자동 선택
  python manage.py create_owner --list_restaurants     # 레스토랑 목록 조회
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "카카오 ID로 점주 OwnerProfile을 생성합니다."

    def add_arguments(self, parser):
        parser.add_argument("--kakao_id", type=str, help="카카오 사용자 ID")
        parser.add_argument("--restaurant_id", type=int, help="연결할 restaurant_id")
        parser.add_argument("--list_restaurants", action="store_true", help="레스토랑 목록 출력")
        parser.add_argument("--list_users", action="store_true", help="유저 목록 출력")

    def handle(self, *args, **options):
        from restaurants.models import AffiliateRestaurant
        from dashboard.models import OwnerProfile

        if options["list_restaurants"]:
            restaurants = AffiliateRestaurant.objects.all()[:20]
            self.stdout.write("=== AffiliateRestaurant 목록 ===")
            for r in restaurants:
                self.stdout.write(f"  ID={r.restaurant_id}  {r}")
            return

        if options["list_users"]:
            users = User.objects.all()[:20]
            self.stdout.write("=== User 목록 ===")
            for u in users:
                self.stdout.write(f"  ID={u.id}  kakao_id={getattr(u, 'kakao_id', '?')}  {u}")
            return

        kakao_id = options.get("kakao_id")
        if not kakao_id:
            self.stderr.write("--kakao_id 가 필요합니다.")
            return

        # User 찾기
        try:
            user = User.objects.get(kakao_id=kakao_id)
        except User.DoesNotExist:
            self.stderr.write(f"kakao_id={kakao_id} 에 해당하는 User가 없습니다.")
            self.stderr.write("카카오 로그인을 한 번 완료한 후 다시 실행하세요.")
            return

        self.stdout.write(f"User 찾음: {user} (pk={user.pk})")

        # Restaurant 선택
        restaurant_id = options.get("restaurant_id")
        if restaurant_id:
            try:
                restaurant = AffiliateRestaurant.objects.get(restaurant_id=restaurant_id)
            except AffiliateRestaurant.DoesNotExist:
                self.stderr.write(f"restaurant_id={restaurant_id} 가 존재하지 않습니다.")
                return
        else:
            restaurant = AffiliateRestaurant.objects.first()
            if not restaurant:
                self.stderr.write("AffiliateRestaurant가 하나도 없습니다.")
                return
            self.stdout.write(f"restaurant_id 미지정 → 첫 번째 레스토랑 사용: {restaurant}")

        # OwnerProfile 생성 or 업데이트
        profile, created = OwnerProfile.objects.get_or_create(
            user=user,
            defaults={"restaurant": restaurant, "tier": "FREE", "is_active": True},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"✅ OwnerProfile 생성 완료: {profile}"))
        else:
            self.stdout.write(self.style.WARNING(f"이미 존재하는 OwnerProfile: {profile}"))
