import json
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import router, transaction
from django.utils import timezone

from restaurants.models import AffiliateRestaurant
from coupons.models import (
    Campaign,
    CouponType,
    RestaurantCouponBenefit,
    CouponRestaurantExclusion,
)


class Command(BaseCommand):
    help = (
        "앱 접속 시 발급되는 쿠폰(App Open Coupon)을 위한 Campaign / "
        "RestaurantCouponBenefit / CouponRestaurantExclusion 을 설정합니다.\n"
        "- 지정한 기간(start/end) 동안만 유효한 Campaign 생성/업데이트\n"
        "- 지정한 restaurant_id 들에 대해 친구초대 쿠폰(REFERRAL_BONUS_REFEREE)의 "
        "혜택/타이틀을 복사하여 앱 접속 쿠폰용 RestaurantCouponBenefit 생성\n"
        "- 선택적으로 --exclusive 를 사용하면 지정된 식당 이외에는 "
        "해당 쿠폰 타입이 발급되지 않도록 CouponRestaurantExclusion 을 설정"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--coupon-type-code",
            type=str,
            required=True,
            help="앱 접속 시 발급될 CouponType 코드 (예: APP_OPEN_3000 또는 기존 코드)",
        )
        parser.add_argument(
            "--campaign-code",
            type=str,
            required=True,
            help="앱 접속 쿠폰용 Campaign 코드 (예: APP_OPEN_EVENT_202501)",
        )
        parser.add_argument(
            "--campaign-name",
            type=str,
            help="Campaign 이름 (지정하지 않으면 campaign-code 를 그대로 사용)",
        )
        parser.add_argument(
            "--campaign-type",
            type=str,
            default="FLASH",
            help="Campaign 유형 (기본값: FLASH, 예: SIGNUP / REFERRAL / FLASH)",
        )
        parser.add_argument(
            "--start",
            type=str,
            help="캠페인 시작 시각 (예: '2025-01-01' 또는 '2025-01-01T00:00:00')",
        )
        parser.add_argument(
            "--end",
            type=str,
            help="캠페인 종료 시각 (예: '2025-01-31' 또는 '2025-01-31T23:59:59')",
        )
        parser.add_argument(
            "--restaurant-id",
            type=int,
            action="append",
            dest="restaurant_ids",
            help="앱 접속 쿠폰이 적용될 restaurant_id (여러 번 지정 가능)",
        )
        parser.add_argument(
            "--subtitle",
            type=str,
            default="",
            help=(
                "앱 접속 쿠폰 서브타이틀. 지정하지 않으면 친구초대 쿠폰 서브타이틀을 복사합니다."
            ),
        )
        parser.add_argument(
            "--exclusive",
            action="store_true",
            help=(
                "지정된 restaurant_id 외의 모든 식당을 CouponRestaurantExclusion 에 등록하여 "
                "해당 쿠폰 타입(APP_OPEN용)이 그 식당들에서는 발급되지 않도록 설정합니다."
            ),
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

    def _parse_datetime(self, value: str | None, field_name: str):
        if not value:
            return None
        try:
            # Python 3.11+ 에서 지원하는 fromisoformat 을 활용 (YYYY-MM-DD 또는 ISO8601)
            dt = datetime.fromisoformat(value)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt
        except Exception as exc:  # noqa: BLE001
            raise CommandError(
                f"{field_name} 값 '{value}' 을(를) datetime 으로 파싱할 수 없습니다. "
                "예: '2025-01-01' 또는 '2025-01-01T00:00:00'"
            ) from exc

    def _confirm(self, message: str, *, no_input: bool):
        if no_input:
            return
        self.stdout.write(self.style.WARNING(message))
        confirm = input('계속하려면 "yes" 를 입력하세요: ')
        if confirm.strip().lower() != "yes":
            raise CommandError("사용자에 의해 작업이 취소되었습니다.")

    def _load_coupon_type(self, code: str, alias: str):
        try:
            return CouponType.objects.using(alias).get(code=code)
        except CouponType.DoesNotExist as exc:  # noqa: BLE001
            raise CommandError(
                f"CouponType(code='{code}') 를 찾을 수 없습니다. 먼저 생성해 주세요."
            ) from exc

    def _ensure_campaign(
        self,
        *,
        alias: str,
        code: str,
        name: str | None,
        type_: str,
        start,
        end,
        dry_run: bool,
    ):
        defaults = {
            "name": name or code,
            "type": type_,
            "active": True,
            "start_at": start,
            "end_at": end,
            "rules_json": {},
        }

        if dry_run:
            # datetime 은 json.dumps 가 바로 직렬화하지 못하므로 문자열로 변환해서 출력
            debug_defaults = {
                **defaults,
                "start_at": start.isoformat() if start else None,
                "end_at": end.isoformat() if end else None,
            }
            self.stdout.write(
                "[DRY-RUN] Campaign 설정 예정 - "
                f"code={code}, defaults={json.dumps(debug_defaults, ensure_ascii=False)}"
            )
            return None, False

        camp, created = Campaign.objects.using(alias).update_or_create(
            code=code,
            defaults=defaults,
        )
        return camp, created

    def _copy_referral_benefit_to_app_open(
        self,
        *,
        alias: str,
        restaurant_id: int,
        app_open_ct: CouponType,
        subtitle_override: str,
        dry_run: bool,
    ):
        """
        친구초대 피추천인 쿠폰(REFERRAL_BONUS_REFEREE)의 RestaurantCouponBenefit 을
        앱 접속 쿠폰 타입으로 복사하되, subtitle 을 필요 시 덮어쓴다.
        """
        ref_benefit = (
            RestaurantCouponBenefit.objects.using(alias)
            .select_related("coupon_type")
            .filter(
                coupon_type__code="REFERRAL_BONUS_REFEREE",
                restaurant_id=restaurant_id,
            )
            .first()
        )

        if not ref_benefit:
            self.stdout.write(
                self.style.WARNING(
                    "restaurant_id=%s 에 대해 REFERRAL_BONUS_REFEREE "
                    "RestaurantCouponBenefit 이 없어 건너뜁니다." % restaurant_id
                )
            )
            return None, False

        defaults = {
            "title": ref_benefit.title or app_open_ct.title,
            "subtitle": subtitle_override or ref_benefit.subtitle or "",
            "benefit_json": ref_benefit.benefit_json or app_open_ct.benefit_json,
            "active": True,
        }

        if dry_run:
            self.stdout.write(
                "[DRY-RUN] RestaurantCouponBenefit 설정 예정 - "
                f"restaurant_id={restaurant_id}, coupon_type={app_open_ct.code}, "
                f"defaults={json.dumps(defaults, ensure_ascii=False)}"
            )
            return None, False

        obj, created = RestaurantCouponBenefit.objects.using(alias).update_or_create(
            coupon_type=app_open_ct,
            restaurant_id=restaurant_id,
            defaults=defaults,
        )
        return obj, created

    def _apply_exclusive_exclusions(
        self,
        *,
        alias: str,
        app_open_ct: CouponType,
        target_restaurant_ids: list[int],
        dry_run: bool,
    ):
        """
        지정된 restaurant_id 목록만 앱 접속 쿠폰 타입 발급 대상이 되도록
        CouponRestaurantExclusion 을 설정한다.
        """
        target_set = set(int(rid) for rid in target_restaurant_ids)
        all_ids = set(
            AffiliateRestaurant.objects.using(alias)
            .values_list("restaurant_id", flat=True)
        )

        to_exclude = sorted(all_ids - target_set)

        if dry_run:
            self.stdout.write(
                "[DRY-RUN] CouponRestaurantExclusion 설정 예정 - "
                f"coupon_type={app_open_ct.code}, exclude_restaurant_ids={to_exclude}"
            )
            return

        # 대상 식당들에 대해서는 기존 exclusion 제거
        CouponRestaurantExclusion.objects.using(alias).filter(
            coupon_type=app_open_ct,
            restaurant_id__in=target_set,
        ).delete()

        # 그 외 식당들에 대해서는 exclusion 추가/유지
        for rid in to_exclude:
            CouponRestaurantExclusion.objects.using(alias).update_or_create(
                coupon_type=app_open_ct,
                restaurant_id=rid,
                defaults={},
            )

        self.stdout.write(
            self.style.SUCCESS(
                "exclusive 모드 적용 완료 - coupon_type=%s, excluded_restaurant_ids=%s"
                % (app_open_ct.code, json.dumps(to_exclude))
            )
        )

    @transaction.atomic
    def handle(self, *args, **options):
        coupon_type_code: str = options["coupon_type_code"]
        campaign_code: str = options["campaign_code"]
        campaign_name: str | None = options.get("campaign_name")
        campaign_type: str = options.get("campaign_type") or "FLASH"
        start_raw: str | None = options.get("start")
        end_raw: str | None = options.get("end")
        restaurant_ids: list[int] | None = options.get("restaurant_ids")
        subtitle_override: str = options.get("subtitle") or ""
        exclusive: bool = bool(options.get("exclusive"))
        dry_run: bool = bool(options.get("dry_run"))
        no_input: bool = bool(options.get("no_input"))

        if not restaurant_ids:
            raise CommandError(
                "--restaurant-id 옵션으로 하나 이상의 restaurant_id 를 지정해야 합니다."
            )

        start_at = self._parse_datetime(start_raw, "start")
        end_at = self._parse_datetime(end_raw, "end")

        alias = router.db_for_write(Campaign)

        # 요약 출력 및 확인
        summary_lines = [
            "앱 접속(App Open) 쿠폰 설정을 진행합니다:",
            f" - CouponType: {coupon_type_code}",
            f" - Campaign: code={campaign_code}, name={campaign_name or campaign_code}, type={campaign_type}",
            f" - 기간: start={start_at}, end={end_at}",
            f" - 대상 restaurant_id: {sorted(set(restaurant_ids))}",
            f" - subtitle override: '{subtitle_override}'",
            f" - exclusive 모드: {exclusive}",
            f" - dry-run: {dry_run}",
        ]
        self._confirm("\n".join(summary_lines), no_input=no_input)

        app_open_ct = self._load_coupon_type(coupon_type_code, alias)

        camp, created = self._ensure_campaign(
            alias=alias,
            code=campaign_code,
            name=campaign_name,
            type_=campaign_type,
            start=start_at,
            end=end_at,
            dry_run=dry_run,
        )

        if not dry_run:
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Campaign 생성 완료: code={camp.code}, id={camp.id}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Campaign 업데이트 완료: code={camp.code}, id={camp.id}"
                    )
                )

        # 식당별 RestaurantCouponBenefit 설정
        created_count = 0
        updated_count = 0
        for rid in sorted(set(restaurant_ids)):
            result = self._copy_referral_benefit_to_app_open(
                alias=alias,
                restaurant_id=rid,
                app_open_ct=app_open_ct,
                subtitle_override=subtitle_override,
                dry_run=dry_run,
            )
            if not result:
                continue
            _, is_created = result
            if is_created:
                created_count += 1
            else:
                updated_count += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n[DRY-RUN] 실제로 DB는 변경되지 않았습니다. 위 작업이 실행될 예정입니다."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                "\nRestaurantCouponBenefit 설정 완료 - "
                f"생성: {created_count}개, 업데이트: {updated_count}개"
            )
        )

        # exclusive 모드이면 발급 대상 식당을 지정하고 나머지는 제외 설정
        if exclusive:
            self._apply_exclusive_exclusions(
                alias=alias,
                app_open_ct=app_open_ct,
                target_restaurant_ids=restaurant_ids,
                dry_run=dry_run,
            )

        # 마지막으로, 실제 앱 접속 쿠폰 발급을 위해 참고해야 할 환경변수 안내
        self.stdout.write(
            self.style.WARNING(
                "\n[안내] 이 설정을 앱 접속 쿠폰 발급에 사용하려면 서버 환경변수에 다음을 설정해야 합니다.\n"
                f"  - APP_OPEN_COUPON_TYPE_CODE={coupon_type_code}\n"
                f"  - APP_OPEN_CAMPAIGN_CODE={campaign_code}\n"
                "  - (옵션) APP_OPEN_PERIOD=DAILY 또는 WEEKLY\n"
            )
        )


