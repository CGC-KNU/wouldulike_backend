"""
premium.csv, general.csv에서 PIN 번호가 적힌 식당들의 PIN을 DB에 반영합니다.
MerchantPin.secret 및 AffiliateRestaurant.pin_secret을 업데이트합니다.
"""
import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import router, transaction
from django.utils import timezone

from restaurants.models import AffiliateRestaurant
from coupons.models import MerchantPin


# CSV 식당명 -> DB restaurant_id 매핑 (import_affiliate_coupon_benefits_from_csv와 동일)
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
    "혜화문식당": 245,
    "혜화문 식당": 245,
    "혜화문": 245,
}


def _normalize_name(name: str) -> str:
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


def _parse_pins_from_csv(filepath: Path) -> list[tuple[int, str]]:
    """
    CSV에서 (restaurant_id, pin) 쌍 추출.
    PIN이 비어있거나 숫자가 아니면 제외.
    """
    results: list[tuple[int, str]] = []
    seen: set[int] = set()
    path = Path(filepath).resolve()

    if not path.exists():
        return results

    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip first header
        subheader = next(reader, None)
        name_idx = 1
        pin_idx = 7
        if subheader:
            for i, h in enumerate(subheader):
                h = (h or "").strip()
                if "식당명" in h and not h.startswith("1개"):
                    name_idx = i
                if "PIN" in h and "번호" in h:
                    pin_idx = i

        current_restaurant = None
        for row in reader:
            if len(row) <= max(name_idx, pin_idx):
                continue

            name_cell = (row[name_idx] or "").strip()
            pin_cell = (row[pin_idx] if pin_idx < len(row) else "").strip()

            # 식당명 파싱 (여러 줄/쉼표 분리 처리)
            if name_cell and len(name_cell) > 1:
                parts = re.split(r"[,/]|->", name_cell)
                for part in parts:
                    part = part.strip()
                    if part and len(part) > 1 and not part.isdigit():
                        current_restaurant = part
                        break

            if not current_restaurant:
                continue

            # PIN이 없거나 숫자가 아니면 스킵
            if not pin_cell or not pin_cell.replace(" ", "").isdigit():
                continue

            pin = pin_cell.replace(" ", "")
            rid = _find_restaurant_id(current_restaurant)
            if rid is None:
                continue

            # 같은 식당이 여러 행에 나오면 첫 번째만 사용
            if rid not in seen:
                seen.add(rid)
                results.append((rid, pin))

    return results


class Command(BaseCommand):
    help = "premium.csv, general.csv의 PIN 번호를 DB에 반영"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 DB 업데이트 없이 적용 예정만 출력",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        base_dir = Path(__file__).resolve().parent.parent.parent.parent

        csv_files = [
            base_dir / "premium.csv",
            base_dir / "general.csv",
        ]

        # (restaurant_id, pin) 수집 (나중 파일이 우선, 동일 PIN 여러 식당 허용)
        pin_map: dict[int, str] = {}
        for fp in csv_files:
            for rid, pin in _parse_pins_from_csv(fp):
                pin_map[rid] = pin

        if not pin_map:
            self.stdout.write(self.style.WARNING("CSV에서 PIN이 있는 식당이 없습니다."))
            return

        alias = "cloudsql"

        # DB에 해당 식당이 있는지 확인 (없는 식당은 스킵)
        existing = {
            r["restaurant_id"]: r["name"]
            for r in AffiliateRestaurant.objects.using(alias).filter(
                restaurant_id__in=list(pin_map.keys())
            ).values("restaurant_id", "name")
        }
        pin_map = {rid: pin for rid, pin in pin_map.items() if rid in existing}

        # PIN 유효성 검사
        for rid, pin in pin_map.items():
            if not pin.isdigit():
                raise CommandError(f"restaurant_id={rid}: PIN은 숫자만 허용됩니다. (현재: {pin})")
            if len(pin) < 4:
                raise CommandError(f"restaurant_id={rid}: PIN은 최소 4자리여야 합니다. (현재: {pin})")

        if dry_run:
            self.stdout.write("[DRY-RUN] 적용 예정:")
            for rid in sorted(pin_map.keys()):
                name = existing.get(rid, "?")
                self.stdout.write(f"  {rid}: {name} -> PIN {pin_map[rid]}")
            return

        now = timezone.now()
        updated = 0

        with transaction.atomic(using=alias):
            for rid, pin in pin_map.items():
                period_sec = 30
                try:
                    mp = MerchantPin.objects.using(alias).get(restaurant_id=rid)
                    period_sec = mp.period_sec
                except MerchantPin.DoesNotExist:
                    pass

                MerchantPin.objects.using(alias).update_or_create(
                    restaurant_id=rid,
                    defaults={
                        "algo": "STATIC",
                        "secret": pin,
                        "period_sec": period_sec,
                        "last_rotated_at": now,
                    },
                )
                AffiliateRestaurant.objects.using(alias).filter(restaurant_id=rid).update(
                    pin_secret=pin, pin_updated_at=now
                )
                updated += 1
                name = existing.get(rid, "?")
                self.stdout.write(self.style.SUCCESS(f"  {rid}: {name} -> PIN {pin}"))

        self.stdout.write(self.style.SUCCESS(f"\n총 {updated}개 식당 PIN 반영 완료."))
