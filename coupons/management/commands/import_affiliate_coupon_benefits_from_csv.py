"""
CSV 파일에서 제휴식당 쿠폰 혜택을 RestaurantCouponBenefit으로 import합니다.

- 프리미엄 CSV: Better, 와비사비, 포차1번지먹새통 제외
- 일반 CSV: 고니식탁 제외
- 쿠폰 혜택 X = 발급 없음 (benefit 생성 안 함)
- 여러 행 = 여러 쿠폰 (sort_order로 구분)
- 쿠폰 비고 = notes (사용 조건)
"""
import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import router, transaction

from restaurants.models import AffiliateRestaurant
from coupons.models import CouponType, RestaurantCouponBenefit


# CSV 식당명 -> DB restaurant_id 매핑 (이름 부분 매칭)
NAME_TO_ID = {
    "정든밤": 97,
    "구구포차": 33,
    "통통주먹구이": 145,
    "포차1번지먹새통": 147,
    "스톡홀름샐러드": 143,
    "스톡홀롬샐러드": 143,
    "벨로": 19,
    "닭동가리": 146,
    "마름모식당": 62,
    "주비두루": 144,
    "주비 두루": 144,
    "Better": 148,
    "북성로우동불고기": 266,
    "북성로 우동 불고기": 266,
    "난탄": 285,
    "사랑과평화": 271,
    "와비사비": 284,
    "한끼갈비": 74,
    "고니식탁": 30,
    "대부": 47,
    "대부 대왕유부초밥": 47,
    "부리또익스프레스": 41,
    "다이와스시": 56,
    "고씨네": 249,
}

EXCLUDE_NAMES = {"Better", "와비사비", "포차1번지먹새통", "고니식탁"}

COUPON_TYPES = ["WELCOME_3000", "REFERRAL_BONUS_REFERRER", "REFERRAL_BONUS_REFEREE"]


def _normalize_name(name: str) -> str:
    """식당명 정규화 (공백, 괄호 제거)"""
    if not name:
        return ""
    return re.sub(r"\s+", " ", name.strip())


def _find_restaurant_id(name: str) -> int | None:
    """식당명으로 restaurant_id 찾기"""
    normalized = _normalize_name(name)
    for key, rid in NAME_TO_ID.items():
        if key in normalized or normalized in key:
            return rid
    return None


def _parse_csv_rows(filepath: Path) -> list[dict]:
    """CSV 파싱 - 쿠폰 혜택/비고가 있는 행만 (빈 식당명은 이전 행의 식당에 속함)"""
    rows = []
    current_restaurant = None
    path = Path(filepath).resolve()

    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # skip first header row
        subheader = next(reader, None)  # skip second header row
        name_idx = 1
        benefit_idx = 8
        notes_idx = 9
        if subheader:
            for i, h in enumerate(subheader):
                h = (h or "").strip()
                if "식당명" in h and not h.startswith("1개"):
                    name_idx = i
                # 첫 번째 쿠폰 컬럼만 사용 (i < 12로 기획전 쪽 중복 제외)
                if i < 12 and (h == "쿠폰 혜택" or h == "쿠폰"):
                    benefit_idx = i
                if i < 12 and ("쿠폰 비고" in h or h == "쿠폰 조건"):
                    notes_idx = i

        for row in reader:
            if len(row) <= max(name_idx, benefit_idx, notes_idx):
                continue
            name_cell = (row[name_idx] or "").strip()
            benefit = (row[benefit_idx] if benefit_idx < len(row) else "").strip()
            notes = (row[notes_idx] if notes_idx < len(row) else "").strip()

            if name_cell and len(name_cell) > 1:
                parts = re.split(r"[,/]|->", name_cell)
                for part in parts:
                    part = part.strip()
                    if part and len(part) > 1 and not part.isdigit():
                        current_restaurant = part
                        break

            if not current_restaurant:
                continue

            if benefit.upper() == "X" or not benefit:
                continue

            rid = _find_restaurant_id(current_restaurant)
            if rid is None:
                continue

            if any(ex in current_restaurant for ex in EXCLUDE_NAMES):
                continue

            rows.append({"restaurant_id": rid, "title": benefit, "notes": notes})

    return rows


def _group_by_restaurant(rows: list[dict]) -> dict[int, list[dict]]:
    """restaurant_id별로 그룹화 (같은 식당 여러 쿠폰)"""
    grouped: dict[int, list[dict]] = {}
    for r in rows:
        rid = r["restaurant_id"]
        if rid not in grouped:
            grouped[rid] = []
        grouped[rid].append(r)
    return grouped


class Command(BaseCommand):
    help = "CSV에서 제휴식당 쿠폰 혜택을 RestaurantCouponBenefit으로 import"

    def add_arguments(self, parser):
        parser.add_argument(
            "premium_csv",
            type=str,
            help="프리미엄 CSV 경로",
        )
        parser.add_argument(
            "general_csv",
            type=str,
            help="일반 CSV 경로",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 저장 없이 출력만",
        )

    def handle(self, *args, **options):
        premium_path = Path(options["premium_csv"])
        general_path = Path(options["general_csv"])
        dry_run = options["dry_run"]
        if not premium_path.is_absolute():
            premium_path = Path.cwd() / premium_path
        if not general_path.is_absolute():
            general_path = Path.cwd() / general_path

        if not premium_path.exists():
            raise CommandError(f"파일 없음: {premium_path}")
        if not general_path.exists():
            raise CommandError(f"파일 없음: {general_path}")

        premium_rows = _parse_csv_rows(premium_path.resolve())
        general_rows = _parse_csv_rows(general_path.resolve())

        self.stdout.write(f"프리미엄 파싱: {len(premium_rows)}행, 일반 파싱: {len(general_rows)}행")

        all_rows = premium_rows + general_rows
        grouped = _group_by_restaurant(all_rows)
        self.stdout.write(f"그룹화: {len(grouped)}개 식당, restaurant_ids={list(grouped.keys())}")

        alias = router.db_for_write(RestaurantCouponBenefit)
        # AffiliateRestaurant은 cloudsql 사용 가능
        from django.db import connections

        ar_alias = "cloudsql" if "cloudsql" in connections else "default"
        valid_ids = set(
            AffiliateRestaurant.objects.using(ar_alias)
            .filter(restaurant_id__in=grouped.keys())
            .values_list("restaurant_id", flat=True)
        )
        self.stdout.write(f"DB 매칭: {len(valid_ids)}개 valid_ids={valid_ids}")

        created = updated = 0
        for coupon_type_code in COUPON_TYPES:
            try:
                ct = CouponType.objects.using(alias).get(code=coupon_type_code)
            except CouponType.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"CouponType {coupon_type_code} 없음, 건너뜀"))
                continue

            for restaurant_id in valid_ids:
                benefits = grouped.get(restaurant_id, [])
                if not benefits:
                    continue

                for sort_order, b in enumerate(benefits):
                    if dry_run:
                        self.stdout.write(
                            f"[DRY-RUN] {coupon_type_code} restaurant_id={restaurant_id} "
                            f"sort={sort_order}: {b['title'][:30]}..."
                        )
                        created += 1
                        continue

                    _, was_created = RestaurantCouponBenefit.objects.using(alias).update_or_create(
                        coupon_type=ct,
                        restaurant_id=restaurant_id,
                        sort_order=sort_order,
                        defaults={
                            "title": b["title"][:120],
                            "notes": b["notes"][:500] if b["notes"] else "",
                            "active": True,
                        },
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"완료: 생성 {created}개, 업데이트 {updated}개 "
                f"(식당 {len(valid_ids)}개, dry_run={dry_run})"
            )
        )
