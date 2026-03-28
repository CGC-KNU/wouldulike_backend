"""
CSV 기준으로 제휴식당을 동기화합니다.

- 제휴식당 19개: Better(148), 와비사비(284) 제외 (실제 제휴 아님)
- 쿠폰 발급 17개: 19개 중 포차1번지먹새통(147), 고니식탁(30) 제외
- 19개 제외한 나머지: is_affiliate=FALSE (일반식당으로 취급)
"""
from django.core.management.base import BaseCommand
from django.db import connections, router, transaction

from restaurants.models import AffiliateRestaurant
from coupons.models import CouponRestaurantExclusion

# CSV 기준 (NAME_TO_ID) - Better, 와비사비 제외 → 19개 제휴
AFFILIATE_IDS = [
    19,   # 벨로
    30,   # 고니식탁 (쿠폰 제외)
    33,   # 구구포차
    41,   # 부리또익스프레스
    47,   # 대부
    56,   # 다이와스시
    62,   # 마름모식당
    74,   # 한끼갈비
    97,   # 정든밤
    143,  # 스톡홀름샐러드
    144,  # 주비두루
    145,  # 통통주먹구이
    146,  # 닭동가리
    147,  # 포차1번지먹새통 (쿠폰 제외)
    249,  # 고씨네
    266,  # 북성로우동불고기
    271,  # 사랑과평화
    285,  # 난탄
    245,  # 혜화문식당
]

AFFILIATE_NAMES = {
    19: "벨로",
    30: "고니식탁",
    33: "구구포차",
    41: "부리또익스프레스",
    47: "대부",
    56: "다이와스시",
    62: "마름모식당",
    74: "한끼갈비",
    97: "정든밤",
    143: "스톡홀름샐러드",
    144: "주비두루",
    145: "통통주먹구이",
    146: "닭동가리",
    147: "포차1번지먹새통",
    249: "고씨네",
    266: "북성로우동불고기",
    271: "사랑과평화",
    285: "난탄",
    245: "혜화문식당",
}


class Command(BaseCommand):
    help = "CSV 기준 제휴식당 19개로 동기화 (나머지 제휴 해제)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="실제 변경 없이 미리보기")
        parser.add_argument("--no-input", action="store_true", help="확인 없이 실행")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        no_input = options["no_input"]
        alias = router.db_for_write(AffiliateRestaurant)

        if "cloudsql" not in connections.databases:
            self.stdout.write(self.style.ERROR("cloudsql DB 연결이 필요합니다."))
            return

        # 현재 제휴 식당 조회
        current = set(
            AffiliateRestaurant.objects.using(alias)
            .filter(is_affiliate=True)
            .values_list("restaurant_id", flat=True)
        )
        all_in_table = set(
            AffiliateRestaurant.objects.using(alias).values_list("restaurant_id", flat=True)
        )

        to_affiliate = set(AFFILIATE_IDS)
        to_unlink = all_in_table - to_affiliate
        to_add = to_affiliate - all_in_table

        self.stdout.write(f"\n제휴식당 19개: {sorted(AFFILIATE_IDS)}")
        self.stdout.write(f"현재 is_affiliate=True: {len(current)}개")
        self.stdout.write(f"제휴로 설정할 식당: {len(to_affiliate)}개")
        if to_add:
            self.stdout.write(self.style.WARNING(f"  → DB에 없어 추가 필요: {sorted(to_add)}"))
        if to_unlink:
            self.stdout.write(
                self.style.WARNING(f"  → 제휴 해제할 식당: {sorted(to_unlink)}")
            )

        if not no_input and not dry_run and (to_add or to_unlink):
            confirm = input("\n계속하시겠습니까? [y/N]: ")
            if confirm.lower() != "y":
                self.stdout.write("취소되었습니다.")
                return

        with transaction.atomic(using=alias):
            # 1) 없는 식당 추가
            for rid in sorted(to_add):
                name = AFFILIATE_NAMES.get(rid, f"식당_{rid}")
                if dry_run:
                    self.stdout.write(f"[DRY-RUN] INSERT restaurant_id={rid} name={name}")
                else:
                    AffiliateRestaurant.objects.using(alias).create(
                        restaurant_id=rid,
                        name=name,
                        is_affiliate=True,
                    )
                    self.stdout.write(f"  ✓ 추가: {rid} {name}")

            # 2) 18개 제휴로 설정
            if not dry_run:
                with connections[alias].cursor() as cursor:
                    placeholders = ", ".join(["%s"] * len(AFFILIATE_IDS))
                    cursor.execute(
                        f"UPDATE restaurants_affiliate SET is_affiliate = TRUE WHERE restaurant_id IN ({placeholders})",
                        AFFILIATE_IDS,
                    )
                    self.stdout.write(f"  ✓ is_affiliate=TRUE: {cursor.rowcount}개")

            # 3) 나머지 제휴 해제
            if to_unlink and not dry_run:
                with connections[alias].cursor() as cursor:
                    placeholders = ", ".join(["%s"] * len(to_unlink))
                    cursor.execute(
                        f"UPDATE restaurants_affiliate SET is_affiliate = FALSE WHERE restaurant_id IN ({placeholders})",
                        list(to_unlink),
                    )
                    self.stdout.write(f"  ✓ is_affiliate=FALSE (제휴 해제): {cursor.rowcount}개")

            # 4) 제휴 해제된 식당의 CouponRestaurantExclusion 정리 (152, 153 등)
            excl_alias = router.db_for_write(CouponRestaurantExclusion)
            if to_unlink and not dry_run:
                deleted, _ = CouponRestaurantExclusion.objects.using(excl_alias).filter(
                    restaurant_id__in=to_unlink
                ).delete()
                if deleted:
                    self.stdout.write(f"  ✓ CouponRestaurantExclusion 삭제: {deleted}건")

        self.stdout.write(self.style.SUCCESS("\n✅ 동기화 완료"))
