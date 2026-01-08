import json
import secrets
import string

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, router, transaction
from django.utils import timezone

from restaurants.models import AffiliateRestaurant
from coupons.models import (
    CouponType,
    Coupon,
    MerchantPin,
    RestaurantCouponBenefit,
    CouponRestaurantExclusion,
)


class Command(BaseCommand):
    help = (
        "새 제휴 식당을 추가하고, 가입/친구초대/스탬프(5/10개) 보상 쿠폰 내용을 "
        "RestaurantCouponBenefit 으로 등록/업데이트합니다."
    )

    def add_arguments(self, parser):
        # 식당 기본 정보
        parser.add_argument(
            "--restaurant-id",
            type=int,
            help="제휴 식당 restaurant_id (PK). 지정하지 않으면 자동으로 미사용 ID를 배정합니다.",
        )
        parser.add_argument(
            "--name",
            type=str,
            help="제휴 식당 이름 (새로 생성할 때 필수)",
        )
        parser.add_argument(
            "--description",
            type=str,
            default="",
            help="제휴 식당 설명 (선택)",
        )
        parser.add_argument(
            "--address",
            type=str,
            help="제휴 식당 주소 (선택, restaurants_affiliate.address)",
        )
        parser.add_argument(
            "--category",
            type=str,
            help="제휴 식당 카테고리/업종 (선택, restaurants_affiliate.category)",
        )
        parser.add_argument(
            "--zone",
            type=str,
            help="제휴 식당 권역/상권 정보 (선택, restaurants_affiliate.zone)",
        )
        parser.add_argument(
            "--phone-number",
            type=str,
            help="제휴 식당 전화번호 (선택, restaurants_affiliate.phone_number)",
        )
        parser.add_argument(
            "--url",
            type=str,
            help="제휴 식당 웹/지도 URL (선택, restaurants_affiliate.url)",
        )
        parser.add_argument(
            "--pin",
            type=str,
            help="해당 제휴 식당용 고정 PIN 코드 (숫자 문자열). 생략하면 새 식당 생성 시 랜덤 4자리 PIN 자동 생성.",
        )

        parser.add_argument(
            "--image-url",
            action="append",
            help=(
                "제휴 식당 사진용 S3 이미지 URL. 여러 번 지정하면 s3_image_urls 배열로 모두 저장됩니다. "
                "(예: --image-url URL1 --image-url URL2)"
            ),
        )

        # 공통 옵션
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제로 DB를 수정하지 않고, 어떤 작업이 수행될지 출력만 합니다.",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="확인 프롬프트 없이 바로 실행합니다.",
        )
        parser.add_argument(
            "--stamp-only",
            action="store_true",
            help=(
                "이 식당을 스탬프 전용으로 설정합니다. "
                "신규가입/친구초대/특정 이벤트(WELCOME_3000, REFERRAL_BONUS_*, FINAL_EXAM_SPECIAL) "
                "쿠폰 발급 대상에서 제외합니다."
            ),
        )

        # 신규가입 쿠폰 (WELCOME_3000)
        parser.add_argument(
            "--signup-title",
            type=str,
            help="신규가입 쿠폰 타이틀 (CouponType=WELCOME_3000)",
        )
        parser.add_argument(
            "--signup-subtitle",
            type=str,
            default="",
            help="신규가입 쿠폰 서브타이틀",
        )
        parser.add_argument(
            "--signup-benefit-json",
            type=str,
            help='신규가입 쿠폰 benefit_json (예: \'{"type": "fixed", "value": 0}\')',
        )

        # 친구초대 쿠폰 (추천인/피추천인 공통 문구)
        parser.add_argument(
            "--referral-title",
            type=str,
            help="친구초대 쿠폰 타이틀 (REFERRAL_BONUS_REFERRER/REFERRAL_BONUS_REFEREE 공통)",
        )
        parser.add_argument(
            "--referral-subtitle",
            type=str,
            default="",
            help="친구초대 쿠폰 서브타이틀",
        )
        parser.add_argument(
            "--referral-benefit-json",
            type=str,
            help='친구초대 쿠폰 benefit_json (예: \'{"type": "fixed", "value": 0}\')',
        )

        # 스탬프 5개 보상 (STAMP_REWARD_5)
        parser.add_argument(
            "--stamp5-title",
            type=str,
            help="스탬프 5개 보상 쿠폰 타이틀 (STAMP_REWARD_5)",
        )
        parser.add_argument(
            "--stamp5-subtitle",
            type=str,
            default="",
            help="스탬프 5개 보상 쿠폰 서브타이틀",
        )
        parser.add_argument(
            "--stamp5-benefit-json",
            type=str,
            help='스탬프 5개 보상 benefit_json (예: \'{"type": "fixed", "value": 0}\')',
        )

        # 스탬프 10개 보상 (STAMP_REWARD_10)
        parser.add_argument(
            "--stamp10-title",
            type=str,
            help="스탬프 10개 보상 쿠폰 타이틀 (STAMP_REWARD_10)",
        )
        parser.add_argument(
            "--stamp10-subtitle",
            type=str,
            default="",
            help="스탬프 10개 보상 쿠폰 서브타이틀",
        )
        parser.add_argument(
            "--stamp10-benefit-json",
            type=str,
            help='스탬프 10개 보상 benefit_json (예: \'{"type": "fixed", "value": 0}\')',
        )

    def _parse_json(self, value: str | None, field_name: str):
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValueError("JSON object여야 합니다 (예: {'type': 'fixed', 'value': 0})")
            return parsed
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"{field_name} 에 잘못된 JSON 이 입력되었습니다: {exc}") from exc

    def _generate_next_restaurant_id(self) -> int:
        """현재 사용 중인 restaurant_id 중 최댓값 + 1 을 반환합니다."""
        alias = router.db_for_write(AffiliateRestaurant)
        max_id = (
            AffiliateRestaurant.objects.using(alias)
            .order_by("-restaurant_id")
            .values_list("restaurant_id", flat=True)
            .first()
        )
        return (max_id or 0) + 1

    def _get_or_create_restaurant(self, restaurant_id: int, name: str | None, description: str):
        restaurant = AffiliateRestaurant.objects.filter(restaurant_id=restaurant_id).first()
        if restaurant:
            updates: dict[str, object] = {}
            if name and restaurant.name != name:
                updates["name"] = name
            # description 은 빈 문자열/None 도 허용
            if description is not None and description != (restaurant.description or ""):
                updates["description"] = description or ""
            if updates:
                AffiliateRestaurant.objects.filter(restaurant_id=restaurant_id).update(**updates)
                restaurant.refresh_from_db()
            return restaurant, False

        if not name:
            raise CommandError(
                f"restaurant_id={restaurant_id} 가 존재하지 않습니다. "
                "--name 을 지정하여 새 제휴 식당을 생성하거나, 미리 DB에 등록하세요."
            )

        restaurant = AffiliateRestaurant(
            restaurant_id=restaurant_id,
            name=name,
            description=description or "",
        )
        restaurant.save()
        return restaurant, True

    def _generate_unique_pin(self, *, length: int = 4, alias: str = "cloudsql") -> str:
        """이미 사용 중인 PIN 을 피해서 고유한 숫자 PIN 을 생성합니다."""
        if length < 4:
            raise CommandError("PIN 길이는 최소 4자리 이상이어야 합니다.")

        used = set(
            MerchantPin.objects.using(alias)
            .exclude(secret__isnull=True)
            .values_list("secret", flat=True)
        )
        used.update(
            pin
            for pin in AffiliateRestaurant.objects.using(alias)
            .exclude(pin_secret__isnull=True)
            .values_list("pin_secret", flat=True)
        )
        used.discard(None)

        alphabet = string.digits
        for _ in range(100):
            candidate = "".join(secrets.choice(alphabet) for _ in range(length))
            if candidate not in used:
                return candidate

        raise CommandError("여러 번 시도했지만 고유한 PIN 을 생성하지 못했습니다.")

    def _ensure_pin(
        self,
        *,
        restaurant_id: int,
        pin: str | None,
        dry_run: bool,
    ):
        """식당 PIN 을 설정하거나 검증합니다.

        - pin 이 주어지면: 형식/중복 검사 후 그대로 사용
        - pin 이 없으면: 아직 PIN 이 없다면 새 랜덤 PIN 생성
        """
        alias = router.db_for_write(Coupon)

        # 이미 PIN 이 있는지 확인 (중복 재생성 방지)
        existing_mp = (
            MerchantPin.objects.using(alias)
            .filter(restaurant_id=restaurant_id)
            .first()
        )
        existing_pin = existing_mp.secret if existing_mp and existing_mp.secret else None
        if not existing_pin:
            existing_pin = (
                AffiliateRestaurant.objects.using(alias)
                .filter(restaurant_id=restaurant_id)
                .values_list("pin_secret", flat=True)
                .first()
            )

        if not pin and existing_pin and not dry_run:
            # 기존 PIN 이 있고, 명시적으로 새 PIN 을 지정하지 않은 경우: 그대로 사용
            return

        if pin:
            if not pin.isdigit():
                raise CommandError("PIN 은 숫자로만 구성돼야 합니다.")
            if len(pin) < 4:
                raise CommandError("PIN 길이는 최소 4자리 이상이어야 합니다.")

            # 다른 식당과 중복 여부 검사
            conflict_mp = (
                MerchantPin.objects.using(alias)
                .filter(secret=pin)
                .exclude(restaurant_id=restaurant_id)
                .exists()
            )
            conflict_aff = (
                AffiliateRestaurant.objects.using(alias)
                .filter(pin_secret=pin)
                .exclude(restaurant_id=restaurant_id)
                .exists()
            )
            if conflict_mp or conflict_aff:
                raise CommandError("이미 다른 제휴 식당에서 사용 중인 PIN 입니다.")

            final_pin = pin
        else:
            # pin 이 주어지지 않은 경우: 필요하면 새 PIN 생성
            final_pin = self._generate_unique_pin(length=4, alias=alias)

        if dry_run:
            self.stdout.write(
                f"[DRY-RUN] PIN 설정 예정 - restaurant_id={restaurant_id} pin={final_pin}"
            )
            return

        now = timezone.now()
        period_sec = existing_mp.period_sec if existing_mp else 30

        with transaction.atomic(using=alias):
            MerchantPin.objects.using(alias).update_or_create(
                restaurant_id=restaurant_id,
                defaults={
                    "algo": "STATIC",
                    "secret": final_pin,
                    "period_sec": period_sec,
                    "last_rotated_at": now,
                },
            )
            AffiliateRestaurant.objects.using(alias).filter(
                restaurant_id=restaurant_id
            ).update(pin_secret=final_pin, pin_updated_at=now)

        # 실제 실행 시 최종 PIN 을 터미널에 출력하여 확인할 수 있도록 함
        self.stdout.write(
            self.style.SUCCESS(
                f"PIN 설정 완료 - restaurant_id={restaurant_id} pin={final_pin}"
            )
        )

    def _upsert_benefit(
        self,
        *,
        restaurant_id: int,
        coupon_type_code: str,
        title: str | None,
        subtitle: str,
        benefit_json_str: str | None,
        dry_run: bool,
    ):
        if not title and not benefit_json_str:
            # 이 쿠폰 타입에 대해서는 아무 것도 설정하지 않음
            return None

        try:
            ct = CouponType.objects.get(code=coupon_type_code)
        except CouponType.DoesNotExist:
            raise CommandError(f"CouponType(code='{coupon_type_code}') 를 찾을 수 없습니다.")

        benefit_json = self._parse_json(benefit_json_str, f"{coupon_type_code} benefit_json")

        defaults = {
            "title": title or ct.title,
            "subtitle": subtitle or "",
            "benefit_json": benefit_json,
            "active": True,
        }

        if dry_run:
            self.stdout.write(
                f"[DRY-RUN] RestaurantCouponBenefit 설정 예정 - "
                f"restaurant_id={restaurant_id}, coupon_type={coupon_type_code}, defaults={defaults}"
            )
            return None

        obj, created = RestaurantCouponBenefit.objects.update_or_create(
            coupon_type=ct,
            restaurant_id=restaurant_id,
            defaults=defaults,
        )
        return obj, created

    @transaction.atomic
    def handle(self, *args, **options):
        restaurant_id: int | None = options.get("restaurant_id")
        name: str | None = options.get("name")
        description: str = options.get("description") or ""
        address: str | None = options.get("address")
        category: str | None = options.get("category")
        zone: str | None = options.get("zone")
        phone_number: str | None = options.get("phone_number")
        url: str | None = options.get("url")
        image_urls: list[str] | None = options.get("image_url")
        pin: str | None = options.get("pin")
        dry_run: bool = options["dry_run"]
        no_input: bool = options["no_input"]
        stamp_only: bool = options["stamp_only"]

        # restaurant_id 자동 배정
        if restaurant_id is None:
            if dry_run:
                # DRY-RUN 상태에서도 실제와 동일한 방식으로 ID를 계산
                tmp_id = self._generate_next_restaurant_id()
                self.stdout.write(
                    f"[DRY-RUN] restaurant_id 미지정: 다음 미사용 ID {tmp_id} 를 사용할 예정입니다."
                )
                restaurant_id = tmp_id
            else:
                restaurant_id = self._generate_next_restaurant_id()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"restaurant_id 가 지정되지 않아, 다음 미사용 ID {restaurant_id} 를 배정했습니다."
                    )
                )

        # 어떤 쿠폰 타입이 설정 대상인지 미리 체크 (있으면 쿠폰 설정, 없으면 건너뜀)
        signup_configured = bool(
            options.get("signup_title") or options.get("signup_benefit_json")
        )
        referral_configured = bool(
            options.get("referral_title") or options.get("referral_benefit_json")
        )
        stamp5_configured = bool(
            options.get("stamp5_title") or options.get("stamp5_benefit_json")
        )
        stamp10_configured = bool(
            options.get("stamp10_title") or options.get("stamp10_benefit_json")
        )

        has_any_benefit = any(
            [signup_configured, referral_configured, stamp5_configured, stamp10_configured]
        )

        if has_any_benefit and not dry_run and not no_input:
            lines: list[str] = [
                f"식당 ID {restaurant_id} 에 대해 제휴 식당 및 쿠폰 내용을 설정합니다."
            ]
            if signup_configured:
                lines.append(" - 신규가입: WELCOME_3000")
            if referral_configured:
                lines.append(" - 친구초대: REFERRAL_BONUS_REFERRER / REFERRAL_BONUS_REFEREE")
            if stamp5_configured or stamp10_configured:
                stamp_types: list[str] = []
                if stamp5_configured:
                    stamp_types.append("STAMP_REWARD_5")
                if stamp10_configured:
                    stamp_types.append("STAMP_REWARD_10")
                joined = " / ".join(stamp_types)
                lines.append(f" - 스탬프 보상: {joined}")

            message = "\n".join(lines) + "\n"
            self.stdout.write(self.style.WARNING(message))
            confirm = input('계속하려면 "yes" 를 입력하세요: ')
            if confirm.lower() != "yes":
                raise CommandError("작업이 취소되었습니다.")

        # 1) 제휴 식당 생성/조회
        if dry_run:
            existing = AffiliateRestaurant.objects.filter(restaurant_id=restaurant_id).first()
            if existing:
                self.stdout.write(
                    f"[DRY-RUN] 기존 제휴 식당 사용 - restaurant_id={restaurant_id}, name='{existing.name}'"
                )
                restaurant = existing
                created = False
            else:
                self.stdout.write(
                    f"[DRY-RUN] 새 제휴 식당 생성 예정 - restaurant_id={restaurant_id}, name='{name}'"
                )
                restaurant = None
                created = True
        else:
            restaurant, created = self._get_or_create_restaurant(
                restaurant_id=restaurant_id,
                name=name,
                description=description,
            )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"제휴 식당 생성 완료: restaurant_id={restaurant_id}, name='{name}'"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"기존 제휴 식당 사용: restaurant_id={restaurant_id}, name='{restaurant.name}'"
                )
            )

        # 4-a) 스탬프 전용 식당 설정: 지정된 쿠폰 타입에서 제외
        if stamp_only:
            excluded_codes = [
                "WELCOME_3000",
                "REFERRAL_BONUS_REFERRER",
                "REFERRAL_BONUS_REFEREE",
                "FINAL_EXAM_SPECIAL",
            ]
            alias = router.db_for_write(CouponRestaurantExclusion)
            if dry_run:
                self.stdout.write(
                    "[DRY-RUN] 스탬프 전용 식당 설정 예정 - "
                    f"restaurant_id={restaurant_id}, excluded_coupon_types={excluded_codes}"
                )
            else:
                for code in excluded_codes:
                    try:
                        ct = CouponType.objects.using(alias).get(code=code)
                    except CouponType.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(
                                f"스탬프 전용 설정: CouponType(code='{code}') 를 찾을 수 없어 건너뜁니다."
                            )
                        )
                        continue
                    CouponRestaurantExclusion.objects.using(alias).update_or_create(
                        coupon_type=ct,
                        restaurant_id=restaurant_id,
                        defaults={},
                    )
                self.stdout.write(
                    self.style.SUCCESS(
                        "스탬프 전용 식당으로 설정되었습니다: "
                        f"restaurant_id={restaurant_id}, excluded_coupon_types={excluded_codes}"
                    )
                )

        # 2) 식당 PIN 설정
        # - 새로 생성된 식당: pin 이 없으면 랜덤 생성
        # - 기존 식당: pin 옵션이 주어졌을 때만 변경
        if created:
            self._ensure_pin(restaurant_id=restaurant_id, pin=pin, dry_run=dry_run)
        elif pin is not None:
            self._ensure_pin(restaurant_id=restaurant_id, pin=pin, dry_run=dry_run)

        # 3) 제휴 식당 상세 정보(restaurants_affiliate) 설정/업데이트
        fields_to_update: dict[str, object] = {}
        if address:
            fields_to_update["address"] = address
        if category:
            fields_to_update["category"] = category
        if zone:
            fields_to_update["zone"] = zone
        if phone_number:
            fields_to_update["phone_number"] = phone_number
        if url:
            fields_to_update["url"] = url
        if image_urls:
            fields_to_update["s3_image_urls"] = image_urls

        if fields_to_update:
            alias = router.db_for_write(AffiliateRestaurant)
            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN] 제휴 식당 필드 업데이트 예정 - "
                    f"restaurant_id={restaurant_id}, updates={fields_to_update}"
                )
            else:
                set_clauses = []
                params: list[object] = []
                for col, val in fields_to_update.items():
                    set_clauses.append(f"{col} = %s")
                    params.append(val)
                params.append(restaurant_id)
                set_sql = ", ".join(set_clauses)
                sql = f"UPDATE restaurants_affiliate SET {set_sql} WHERE restaurant_id = %s"
                with connections[alias].cursor() as cursor:
                    cursor.execute(sql, params)
                    if cursor.rowcount == 0:
                        self.stdout.write(
                            self.style.WARNING(
                                f"restaurants_affiliate 에 restaurant_id={restaurant_id} 행이 없어 "
                                "상세 정보를 업데이트하지 못했습니다."
                            )
                        )

        # 5) 쿠폰 내용 설정
        results = []

        # 신규가입 (WELCOME_3000)
        results.append(
            self._upsert_benefit(
                restaurant_id=restaurant_id,
                coupon_type_code="WELCOME_3000",
                title=options.get("signup_title"),
                subtitle=options.get("signup_subtitle") or "",
                benefit_json_str=options.get("signup_benefit_json"),
                dry_run=dry_run,
            )
        )

        # 친구초대 (추천인/피추천인 동일 문구)
        for ct_code in ["REFERRAL_BONUS_REFERRER", "REFERRAL_BONUS_REFEREE"]:
            results.append(
                self._upsert_benefit(
                    restaurant_id=restaurant_id,
                    coupon_type_code=ct_code,
                    title=options.get("referral_title"),
                    subtitle=options.get("referral_subtitle") or "",
                    benefit_json_str=options.get("referral_benefit_json"),
                    dry_run=dry_run,
                )
            )

        # 스탬프 5개 (STAMP_REWARD_5)
        results.append(
            self._upsert_benefit(
                restaurant_id=restaurant_id,
                coupon_type_code="STAMP_REWARD_5",
                title=options.get("stamp5_title"),
                subtitle=options.get("stamp5_subtitle") or "",
                benefit_json_str=options.get("stamp5_benefit_json"),
                dry_run=dry_run,
            )
        )

        # 스탬프 10개 (STAMP_REWARD_10)
        results.append(
            self._upsert_benefit(
                restaurant_id=restaurant_id,
                coupon_type_code="STAMP_REWARD_10",
                title=options.get("stamp10_title"),
                subtitle=options.get("stamp10_subtitle") or "",
                benefit_json_str=options.get("stamp10_benefit_json"),
                dry_run=dry_run,
            )
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] 실제로 DB는 변경되지 않았습니다."))
            return

        # 요약 출력
        created_count = sum(1 for r in results if r and r[1])
        updated_count = sum(1 for r in results if r and not r[1])

        self.stdout.write(
            self.style.SUCCESS(
                f"\nRestaurantCouponBenefit 설정 완료 - "
                f"생성: {created_count}개, 업데이트: {updated_count}개"
            )
        )


