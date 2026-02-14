import json

from django.core.management.base import BaseCommand, CommandError
from django.db import router, transaction

from restaurants.models import AffiliateRestaurant
from coupons.models import CouponType, RestaurantCouponBenefit


class Command(BaseCommand):
    help = (
        "특정 식당 ID의 신규가입, 친구초대, 스탬프(5/10개) 보상 쿠폰 내용을 "
        "RestaurantCouponBenefit으로 업데이트합니다."
    )

    def add_arguments(self, parser):
        # 필수 인자
        parser.add_argument(
            "--restaurant-id",
            type=int,
            required=True,
            help="제휴 식당 restaurant_id (필수)",
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
            help='신규가입 쿠폰 benefit_json (예: \'{"type": "fixed", "value": 5000}\')',
        )

        # 친구초대 쿠폰 - 추천인 (REFERRAL_BONUS_REFERRER)
        parser.add_argument(
            "--referrer-title",
            type=str,
            help="친구초대 쿠폰 타이틀 - 추천인용 (REFERRAL_BONUS_REFERRER)",
        )
        parser.add_argument(
            "--referrer-subtitle",
            type=str,
            default="",
            help="친구초대 쿠폰 서브타이틀 - 추천인용",
        )
        parser.add_argument(
            "--referrer-benefit-json",
            type=str,
            help='친구초대 쿠폰 benefit_json - 추천인용 (예: \'{"type": "fixed", "value": 5000}\')',
        )

        # 친구초대 쿠폰 - 피추천인 (REFERRAL_BONUS_REFEREE)
        parser.add_argument(
            "--referee-title",
            type=str,
            help="친구초대 쿠폰 타이틀 - 피추천인용 (REFERRAL_BONUS_REFEREE)",
        )
        parser.add_argument(
            "--referee-subtitle",
            type=str,
            default="",
            help="친구초대 쿠폰 서브타이틀 - 피추천인용",
        )
        parser.add_argument(
            "--referee-benefit-json",
            type=str,
            help='친구초대 쿠폰 benefit_json - 피추천인용 (예: \'{"type": "fixed", "value": 5000}\')',
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
            help='스탬프 5개 보상 benefit_json (예: \'{"type": "fixed", "value": 5000}\')',
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
            help='스탬프 10개 보상 benefit_json (예: \'{"type": "fixed", "value": 10000}\')',
        )

        # 공통 옵션
        parser.add_argument(
            "--active",
            action="store_true",
            default=True,
            help="쿠폰 활성화 여부 (기본값: True)",
        )
        parser.add_argument(
            "--inactive",
            action="store_true",
            help="쿠폰 비활성화 (--active와 함께 사용 불가)",
        )
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

    def _parse_json(self, value: str | None, field_name: str):
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValueError("JSON object여야 합니다 (예: {'type': 'fixed', 'value': 5000})")
            return parsed
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"{field_name} 에 잘못된 JSON 이 입력되었습니다: {exc}") from exc

    def _upsert_benefit(
        self,
        *,
        restaurant_id: int,
        coupon_type_code: str,
        title: str | None,
        subtitle: str,
        benefit_json_str: str | None,
        active: bool,
        dry_run: bool,
    ):
        """RestaurantCouponBenefit을 생성하거나 업데이트합니다."""
        if not title and not benefit_json_str:
            # 이 쿠폰 타입에 대해서는 아무 것도 설정하지 않음
            return None

        try:
            ct = CouponType.objects.get(code=coupon_type_code)
        except CouponType.DoesNotExist:
            raise CommandError(f"CouponType(code='{coupon_type_code}') 를 찾을 수 없습니다.")

        benefit_json = self._parse_json(benefit_json_str, f"{coupon_type_code} benefit_json")

        # 기존 데이터 조회 (benefit_json 업데이트 시 기존 값 유지)
        existing = RestaurantCouponBenefit.objects.filter(
            coupon_type=ct, restaurant_id=restaurant_id
        ).first()

        defaults = {
            "title": title or (existing.title if existing else ct.title),
            "subtitle": subtitle or (existing.subtitle if existing else ""),
            "benefit_json": benefit_json if benefit_json else (existing.benefit_json if existing else ct.benefit_json),
            "active": active,
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
        restaurant_id: int = options["restaurant_id"]
        dry_run: bool = options["dry_run"]
        no_input: bool = options["no_input"]

        # active 옵션 처리
        if options["inactive"] and options["active"]:
            raise CommandError("--active 와 --inactive 는 동시에 사용할 수 없습니다.")
        active = not options["inactive"]

        # 식당 존재 여부 확인
        alias = router.db_for_read(AffiliateRestaurant)
        try:
            restaurant = AffiliateRestaurant.objects.using(alias).get(restaurant_id=restaurant_id)
        except AffiliateRestaurant.DoesNotExist:
            raise CommandError(
                f"restaurant_id={restaurant_id} 인 제휴 식당을 찾을 수 없습니다. "
                "먼저 제휴 식당을 생성해주세요."
            )

        # 어떤 쿠폰 타입이 설정 대상인지 미리 체크
        has_any_benefit = any(
            [
                options.get("signup_title"),
                options.get("signup_benefit_json"),
                options.get("referrer_title"),
                options.get("referrer_benefit_json"),
                options.get("referee_title"),
                options.get("referee_benefit_json"),
                options.get("stamp5_title"),
                options.get("stamp5_benefit_json"),
                options.get("stamp10_title"),
                options.get("stamp10_benefit_json"),
            ]
        )

        if not has_any_benefit:
            raise CommandError(
                "수정할 쿠폰 내용이 지정되지 않았습니다. "
                "예: --signup-title '새로운 제목' --signup-benefit-json '{\"type\": \"fixed\", \"value\": 5000}'"
            )

        if not dry_run and not no_input:
            self.stdout.write(
                self.style.WARNING(
                    f"식당 ID {restaurant_id} ({restaurant.name}) 에 대해 쿠폰 내용을 수정합니다.\n"
                    f" - 신규가입: WELCOME_3000\n"
                    f" - 친구초대(추천인): REFERRAL_BONUS_REFERRER\n"
                    f" - 친구초대(피추천인): REFERRAL_BONUS_REFEREE\n"
                    f" - 스탬프 보상(5개): STAMP_REWARD_5\n"
                    f" - 스탬프 보상(10개): STAMP_REWARD_10\n"
                )
            )
            confirm = input('계속하려면 "yes" 를 입력하세요: ')
            if confirm.lower() != "yes":
                raise CommandError("작업이 취소되었습니다.")

        self.stdout.write(
            self.style.SUCCESS(f"제휴 식당 확인: restaurant_id={restaurant_id}, name='{restaurant.name}'")
        )

        # 쿠폰 내용 설정
        results = []

        # 신규가입 (WELCOME_3000)
        if options.get("signup_title") or options.get("signup_benefit_json"):
            results.append(
                self._upsert_benefit(
                    restaurant_id=restaurant_id,
                    coupon_type_code="WELCOME_3000",
                    title=options.get("signup_title"),
                    subtitle=options.get("signup_subtitle") or "",
                    benefit_json_str=options.get("signup_benefit_json"),
                    active=active,
                    dry_run=dry_run,
                )
            )

        # 친구초대 - 추천인 (REFERRAL_BONUS_REFERRER)
        if options.get("referrer_title") or options.get("referrer_benefit_json"):
            results.append(
                self._upsert_benefit(
                    restaurant_id=restaurant_id,
                    coupon_type_code="REFERRAL_BONUS_REFERRER",
                    title=options.get("referrer_title"),
                    subtitle=options.get("referrer_subtitle") or "",
                    benefit_json_str=options.get("referrer_benefit_json"),
                    active=active,
                    dry_run=dry_run,
                )
            )

        # 친구초대 - 피추천인 (REFERRAL_BONUS_REFEREE)
        if options.get("referee_title") or options.get("referee_benefit_json"):
            results.append(
                self._upsert_benefit(
                    restaurant_id=restaurant_id,
                    coupon_type_code="REFERRAL_BONUS_REFEREE",
                    title=options.get("referee_title"),
                    subtitle=options.get("referee_subtitle") or "",
                    benefit_json_str=options.get("referee_benefit_json"),
                    active=active,
                    dry_run=dry_run,
                )
            )

        # 스탬프 5개 (STAMP_REWARD_5)
        if options.get("stamp5_title") or options.get("stamp5_benefit_json"):
            results.append(
                self._upsert_benefit(
                    restaurant_id=restaurant_id,
                    coupon_type_code="STAMP_REWARD_5",
                    title=options.get("stamp5_title"),
                    subtitle=options.get("stamp5_subtitle") or "",
                    benefit_json_str=options.get("stamp5_benefit_json"),
                    active=active,
                    dry_run=dry_run,
                )
            )

        # 스탬프 10개 (STAMP_REWARD_10)
        if options.get("stamp10_title") or options.get("stamp10_benefit_json"):
            results.append(
                self._upsert_benefit(
                    restaurant_id=restaurant_id,
                    coupon_type_code="STAMP_REWARD_10",
                    title=options.get("stamp10_title"),
                    subtitle=options.get("stamp10_subtitle") or "",
                    benefit_json_str=options.get("stamp10_benefit_json"),
                    active=active,
                    dry_run=dry_run,
                )
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] 실제로 DB는 변경되지 않았습니다."))
            return

        # 요약 출력
        results = [r for r in results if r is not None]
        created_count = sum(1 for r in results if r[1])
        updated_count = sum(1 for r in results if not r[1])

        self.stdout.write(
            self.style.SUCCESS(
                f"\nRestaurantCouponBenefit 설정 완료 - "
                f"생성: {created_count}개, 업데이트: {updated_count}개"
            )
        )

