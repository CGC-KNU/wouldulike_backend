from unittest.mock import MagicMock, patch
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.db.models.signals import post_save
from django.utils import timezone

from coupons.models import Campaign, Coupon, CouponType, InviteCode, Referral
from coupons.service import (
    accept_referral,
    issue_signup_coupon,
    _build_benefit_snapshot,
    _issue_coupons_for_single_restaurant,
    qualify_referral_and_grant,
    MAX_COUPONS_PER_RESTAURANT,
    ensure_invite_code,
    FULL_AFFILIATE_COUPON_CODE,
    claim_midterm_studylike_coupon,
    MIDTERM_EVENT_COUPON_EXPIRES_AT,
)
from coupons.api.serializers import CouponSerializer
from coupons.models import RestaurantCouponBenefit


class SingleDBRouter:
    def db_for_read(self, model, **hints):
        return "default"

    def db_for_write(self, model, **hints):
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == "default"


settings.DATABASE_ROUTERS = ["coupons.tests.SingleDBRouter"]


class RestaurantAllocationTests(TestCase):
    """신규가입 쿠폰: 한 식당만 발급."""

    @classmethod
    def setUpTestData(cls):
        cls.user_model = get_user_model()
        from coupons import signals as coupon_signals
        post_save.disconnect(coupon_signals.on_user_created, sender=cls.user_model)
        cls.addClassCleanup(post_save.connect, coupon_signals.on_user_created, sender=cls.user_model)
        cls.campaign = Campaign.objects.get(code="SIGNUP_WELCOME")
        cls.coupon_type = CouponType.objects.get(code="WELCOME_3000")

    def _create_user(self, idx: int):
        return self.user_model.objects.create_user(kakao_id=50000 + idx, password="pass")

    def test_signup_coupon_issues_for_single_restaurant(self):
        """신규가입 시 한 식당에 대해서만 쿠폰 발급 (리스트 반환)."""
        user = self._create_user(1)
        mock_coupons = [MagicMock(restaurant_id=101, code="MOCK01")]
        with patch(
            "coupons.service._issue_coupons_for_single_restaurant",
            return_value=mock_coupons,
        ):
            coupons = issue_signup_coupon(user)
        self.assertEqual(len(coupons), 1)
        self.assertEqual(coupons[0].restaurant_id, 101)

    def test_signup_coupon_returns_empty_list_when_no_targets(self):
        """대상 식당이 없으면 빈 리스트 반환."""
        user = self._create_user(2)
        with patch(
            "coupons.service._issue_coupons_for_single_restaurant",
            return_value=[],
        ):
            coupons = issue_signup_coupon(user)
        self.assertEqual(coupons, [])


class SignupCouponSubtitleTests(TestCase):
    """신규가입 쿠폰 subtitle 표기 검증."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_model = get_user_model()
        from coupons import signals as coupon_signals
        post_save.disconnect(coupon_signals.on_user_created, sender=cls.user_model)
        cls.addClassCleanup(post_save.connect, coupon_signals.on_user_created, sender=cls.user_model)

    def test_signup_coupon_builds_benefit_snapshot_with_subtitle(self):
        """
        신규가입 쿠폰은 RestaurantCouponBenefit.subtitle이 benefit_snapshot.subtitle로 내려가야 함.
        (프론트는 benefit.subtitle을 사용)
        """
        ct = CouponType.objects.get(code="WELCOME_3000")
        restaurant_id = 999999  # FK 제약(db_constraint=False)이므로 더미 ID 사용 가능
        benefit = RestaurantCouponBenefit.objects.create(
            coupon_type=ct,
            restaurant_id=restaurant_id,
            sort_order=0,
            title="신규가입 혜택 타이틀",
            subtitle="[신규가입 쿠폰 🎉]",
            benefit_json={},
            notes="",
            active=True,
        )

        snapshot = _build_benefit_snapshot(ct, restaurant_id, benefit=benefit)
        self.assertEqual(snapshot.get("subtitle"), "[신규가입 쿠폰 🎉]")

        user = self.user_model.objects.create_user(kakao_id=91001, password="pass")
        camp = Campaign.objects.get(code="SIGNUP_WELCOME")
        coupon = Coupon.objects.create(
            code="TESTSIGNUP001",
            user=user,
            coupon_type=ct,
            campaign=camp,
            restaurant_id=restaurant_id,
            expires_at=timezone.now() + timedelta(days=1),
            issue_key="TEST:SIGNUP:SUBTITLE",
            benefit_snapshot=snapshot,
        )

        data = CouponSerializer(coupon).data
        self.assertEqual((data.get("benefit") or {}).get("subtitle"), "[신규가입 쿠폰 🎉]")


class ReferralLimitTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_model = get_user_model()
        from coupons import signals as coupon_signals
        post_save.disconnect(coupon_signals.on_user_created, sender=cls.user_model)
        cls.addClassCleanup(post_save.connect, coupon_signals.on_user_created, sender=cls.user_model)

    def setUp(self):
        self.referrer = self.user_model.objects.create_user(kakao_id=1000, password="pass")
        ensure_invite_code(self.referrer)
        self.invite_code = self.referrer.invite_codes.filter(campaign_code__isnull=True).first()

    def test_referral_acceptance_capped_at_five(self):
        with patch("coupons.service._qualify_pending_referrals_locked", return_value=(None, [])):
            for idx in range(5):
                referee = self.user_model.objects.create_user(kakao_id=2000 + idx, password="pass")
                referral, _ = accept_referral(referee=referee, ref_code=self.invite_code.code)
                self.assertEqual(referral.referrer, self.referrer)

        self.assertEqual(Referral.objects.filter(referrer=self.referrer).count(), 5)

        sixth_referee = self.user_model.objects.create_user(kakao_id=3000, password="pass")
        with self.assertRaises(ValidationError) as ctx:
            accept_referral(referee=sixth_referee, ref_code=self.invite_code.code)

        self.assertEqual(ctx.exception.code, "referral_limit_reached")
        self.assertEqual(Referral.objects.filter(referrer=self.referrer).count(), 5)

class ReferralRestaurantAllocationTests(TestCase):
    """친구초대 쿠폰: 추천인·피추천인 각각 한 식당만 발급."""

    @classmethod
    def setUpTestData(cls):
        cls.user_model = get_user_model()
        from coupons import signals as coupon_signals
        post_save.disconnect(coupon_signals.on_user_created, sender=cls.user_model)
        cls.addClassCleanup(post_save.connect, coupon_signals.on_user_created, sender=cls.user_model)
        cls.campaign = Campaign.objects.get(code="REFERRAL")
        cls.referrer_type = CouponType.objects.get(code="REFERRAL_BONUS_REFERRER")
        cls.referee_type = CouponType.objects.get(code="REFERRAL_BONUS_REFEREE")

    def _create_user(self, idx: int):
        return self.user_model.objects.create_user(kakao_id=60000 + idx, password="pass")

    def test_referral_issues_coupons_for_single_restaurant_each(self):
        """친구초대 시 추천인·피추천인 각각 한 식당에 대해서만 쿠폰 발급."""
        referrer = self._create_user(1)
        ensure_invite_code(referrer)
        referee = self._create_user(2)
        code = referrer.invite_codes.filter(campaign_code__isnull=True).values_list("code", flat=True).first()
        # accept_referral 안의 qualify 만 건너뛰어 PENDING 유지 (SQLite 등 Affiliate 테이블 없을 때)
        with patch("coupons.service._qualify_pending_referrals_locked", return_value=(None, [])):
            accept_referral(referee=referee, ref_code=code)

        ref_coupons = [MagicMock(restaurant_id=401, code="REF01")]
        referee_coupons = [MagicMock(restaurant_id=402, code="REE01")]

        def mock_issue(*args, **kwargs):
            coupon_type = kwargs.get("coupon_type") or (args[1] if len(args) > 1 else None)
            if coupon_type and coupon_type.code == "REFERRAL_BONUS_REFERRER":
                return ref_coupons
            return referee_coupons

        with patch(
            "coupons.service._issue_coupons_for_single_restaurant",
            side_effect=mock_issue,
        ):
            _, issued_coupons = qualify_referral_and_grant(referee)

        # 추천인 1개 + 피추천인 1개 = 2개
        self.assertEqual(len(issued_coupons), 2)
        ref_issued = [c for c in issued_coupons if c.code.startswith("REF")]
        referee_issued = [c for c in issued_coupons if c.code.startswith("REE")]
        self.assertEqual(len(ref_issued), 1)
        self.assertEqual(len(referee_issued), 1)


class RefereeBenefitRandomOneTests(TestCase):
    """피추천인(REFERRAL_BONUS_REFEREE): 한 식당에 benefit이 여러 줄이어도 1장만, 그중 무작위 1종."""

    @classmethod
    def setUpTestData(cls):
        cls.user_model = get_user_model()
        from coupons import signals as coupon_signals
        post_save.disconnect(coupon_signals.on_user_created, sender=cls.user_model)
        cls.addClassCleanup(post_save.connect, coupon_signals.on_user_created, sender=cls.user_model)
        cls.campaign = Campaign.objects.get(code="REFERRAL")
        cls.referee_type = CouponType.objects.get(code="REFERRAL_BONUS_REFEREE")

    def setUp(self):
        self.user = self.user_model.objects.create_user(kakao_id=88001, password="pass")
        self.rid = 8801100

    def test_referee_issues_single_coupon_picks_one_of_four(self):
        titles = ["혜택A", "혜택B", "혜택C", "혜택D"]
        for i, title in enumerate(titles):
            RestaurantCouponBenefit.objects.create(
                coupon_type=self.referee_type,
                restaurant_id=self.rid,
                sort_order=i,
                title=title,
                subtitle="",
                benefit_json={},
                active=True,
            )
        with patch("coupons.service._select_restaurant_for_coupon", return_value=self.rid):
            with patch("coupons.service.random.choice", side_effect=lambda seq: seq[2]):
                issued = _issue_coupons_for_single_restaurant(
                    user=self.user,
                    coupon_type=self.referee_type,
                    campaign=self.campaign,
                    issue_key_prefix=f"REFERRAL_REFEREE:{self.user.id}",
                )
        self.assertEqual(len(issued), 1)
        self.assertEqual((issued[0].benefit_snapshot or {}).get("title"), "혜택C")

    def test_referee_one_benefit_row_still_uses_that_one(self):
        RestaurantCouponBenefit.objects.create(
            coupon_type=self.referee_type,
            restaurant_id=self.rid,
            sort_order=0,
            title="단일혜택",
            subtitle="",
            benefit_json={},
            active=True,
        )
        with patch("coupons.service._select_restaurant_for_coupon", return_value=self.rid):
            issued = _issue_coupons_for_single_restaurant(
                user=self.user,
                coupon_type=self.referee_type,
                campaign=self.campaign,
                issue_key_prefix=f"REFERRAL_REFEREE:{self.user.id}",
            )
        self.assertEqual(len(issued), 1)
        self.assertEqual((issued[0].benefit_snapshot or {}).get("title"), "단일혜택")

    def test_hyehwamun_four_rows_one_coupon_nonempty_not_first_only(self):
        """
        혜화문(245)과 같이 피추천 benefit이 4행일 때:
        - 발급은 항상 1장(4장 중복 발급 없음)
        - benefit_snapshot.title 이 비어 있지 않음
        - random.choice 풀은 4행 전체(첫 행만 잘리지 않음)
        - sort_order 0~3 어떤 행이든 선택될 수 있음(고정 첫 행만 아님)
        """
        titles = ["든든한혼밥1", "든든한혼밥2", "얼리어답터", "스탬프교환"]
        for i, title in enumerate(titles):
            RestaurantCouponBenefit.objects.create(
                coupon_type=self.referee_type,
                restaurant_id=self.rid,
                sort_order=i,
                title=title,
                subtitle="[피추천]",
                benefit_json={"note": "x"},
                active=True,
            )
        with patch("coupons.service._select_restaurant_for_coupon", return_value=self.rid):
            for pick_idx in (0, 1, 2, 3):
                u = self.user_model.objects.create_user(kakao_id=88100 + pick_idx, password="pass")
                with patch(
                    "coupons.service.random.choice",
                    side_effect=lambda seq, idx=pick_idx: seq[idx],
                ):
                    issued = _issue_coupons_for_single_restaurant(
                        user=u,
                        coupon_type=self.referee_type,
                        campaign=self.campaign,
                        issue_key_prefix=f"REFERRAL_REFEREE:{u.id}",
                    )
                self.assertEqual(len(issued), 1, f"pick_idx={pick_idx} 일 때도 1장만")
                snap = issued[0].benefit_snapshot or {}
                self.assertTrue(
                    (snap.get("title") or "").strip(),
                    "빈 쿠폰(benefit_snapshot.title 없음)이면 안 됨",
                )
                self.assertEqual(snap.get("title"), titles[pick_idx])
                self.assertEqual(snap.get("subtitle"), "[피추천]")

        mock_choice = MagicMock(side_effect=lambda seq: seq[0])
        u2 = self.user_model.objects.create_user(kakao_id=88199, password="pass")
        with patch("coupons.service._select_restaurant_for_coupon", return_value=self.rid):
            with patch("coupons.service.random.choice", mock_choice):
                _issue_coupons_for_single_restaurant(
                    user=u2,
                    coupon_type=self.referee_type,
                    campaign=self.campaign,
                    issue_key_prefix=f"REFERRAL_REFEREE:{u2.id}",
                )
        mock_choice.assert_called_once()
        pool = mock_choice.call_args[0][0]
        self.assertEqual(len(pool), 4, "choice는 4개 benefit 전체 풀에 대해 호출되어야 함")


class FullAffiliateAndKnulikeCouponTests(TestCase):
    """DONGARILIKE(제휴식당 전체) 및 KNULIKE 추천코드 발급 테스트."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_model = get_user_model()
        from coupons import signals as coupon_signals
        post_save.disconnect(coupon_signals.on_user_created, sender=cls.user_model)
        cls.addClassCleanup(post_save.connect, coupon_signals.on_user_created, sender=cls.user_model)

    def test_full_affiliate_code_issues_coupons(self):
        """DONGARILIKE 코드 입력 시 제휴식당 전체 쿠폰 발급."""
        referee = self.user_model.objects.create_user(kakao_id=70001, password="pass")
        mock_issued = [MagicMock(code="F001", restaurant_id=101, benefit_snapshot={})]
        with patch(
            "coupons.service.issue_full_affiliate_coupons",
            return_value={"coupons": mock_issued, "total_issued": 1, "failed_restaurants": [], "already_issued": False},
        ):
            referral, issued = accept_referral(referee=referee, ref_code=FULL_AFFILIATE_COUPON_CODE)
        self.assertIsNotNone(referral)
        self.assertEqual(referral.campaign_code, "FULL_AFFILIATE_EVENT")
        self.assertGreater(len(issued), 0, "제휴식당 쿠폰이 1개 이상 발급되어야 함")

    def test_full_affiliate_code_duplicate_rejected(self):
        """DONGARILIKE 코드 중복 입력 시 거부."""
        referee = self.user_model.objects.create_user(kakao_id=70002, password="pass")
        mock_issued = [MagicMock(code="F001", restaurant_id=101, benefit_snapshot={})]
        with patch(
            "coupons.service.issue_full_affiliate_coupons",
            return_value={"coupons": mock_issued, "total_issued": 1, "failed_restaurants": [], "already_issued": False},
        ):
            accept_referral(referee=referee, ref_code=FULL_AFFILIATE_COUPON_CODE)
        # 발급되었다고 가정하고 Coupon row를 생성해 중복 체크가 DB에서 걸리게 함
        ct = CouponType.objects.get(code="FULL_AFFILIATE_SPECIAL")
        camp = Campaign.objects.get(code="FULL_AFFILIATE_EVENT")
        Coupon.objects.create(
            code="FULLAFFDUP01",
            user=referee,
            coupon_type=ct,
            campaign=camp,
            restaurant_id=101,
            expires_at=timezone.now() + timedelta(days=7),
            issue_key=f"FULL_AFFILIATE:{referee.id}:101",
            benefit_snapshot={},
        )
        with self.assertRaises(ValidationError) as ctx:
            accept_referral(referee=referee, ref_code=FULL_AFFILIATE_COUPON_CODE)
        self.assertEqual(ctx.exception.code, "full_affiliate_already_issued")

    def test_knulike_code_issues_three_coupons(self):
        """KNULIKE 코드 입력 시 쿠폰 3개 발급."""
        referee = self.user_model.objects.create_user(kakao_id=70003, password="pass")
        mock_issued = [MagicMock(code=f"K{idx}", restaurant_id=200 + idx, benefit_snapshot={}) for idx in range(3)]
        with patch(
            "coupons.service.issue_knulike_coupons",
            return_value={"coupons": mock_issued, "total_issued": 3, "already_issued": False},
        ):
            referral, issued = accept_referral(referee=referee, ref_code="KNULIKE")
        self.assertIsNotNone(referral)
        self.assertEqual(referral.campaign_code, "KNULIKE_EVENT")
        self.assertEqual(len(issued), 3, "KNULIKE는 쿠폰 3개 발급")

    def test_knulike_code_duplicate_rejected(self):
        """KNULIKE 코드 중복 입력 시 거부."""
        referee = self.user_model.objects.create_user(kakao_id=70004, password="pass")
        mock_issued = [MagicMock(code=f"K{idx}", restaurant_id=200 + idx, benefit_snapshot={}) for idx in range(3)]
        with patch(
            "coupons.service.issue_knulike_coupons",
            return_value={"coupons": mock_issued, "total_issued": 3, "already_issued": False},
        ):
            accept_referral(referee=referee, ref_code="KNULIKE")
        ct = CouponType.objects.get(code="KNULIKE")
        camp = Campaign.objects.get(code="KNULIKE_EVENT")
        Coupon.objects.create(
            code="KNULIKEDUP01",
            user=referee,
            coupon_type=ct,
            campaign=camp,
            restaurant_id=201,
            expires_at=timezone.now() + timedelta(days=7),
            issue_key=f"KNULIKE:{referee.id}:201:0",
            benefit_snapshot={},
        )
        with self.assertRaises(ValidationError) as ctx:
            accept_referral(referee=referee, ref_code="KNULIKE")
        self.assertEqual(ctx.exception.code, "knulike_already_issued")


class BoothVisitCouponTests(TestCase):
    """80THANNIVERSARY 추천코드: 전체 제휴식당 중 1개 쿠폰 발급."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_model = get_user_model()
        from coupons import signals as coupon_signals
        post_save.disconnect(coupon_signals.on_user_created, sender=cls.user_model)
        cls.addClassCleanup(post_save.connect, coupon_signals.on_user_created, sender=cls.user_model)

    def test_booth_visit_code_issues_one_coupon_and_sets_subtitle(self):
        referee = self.user_model.objects.create_user(kakao_id=80001, password="pass")
        mock_issued = [MagicMock(code="B001", restaurant_id=101, benefit_snapshot={"subtitle": "[🎁 부스 방문 쿠폰 🎁]"})]
        with patch("coupons.service.issue_booth_visit_coupon", return_value={"coupons": mock_issued, "total_issued": 1, "already_issued": False}):
            referral, issued = accept_referral(referee=referee, ref_code="80THANNIVERSARY")
        self.assertIsNotNone(referral)
        self.assertEqual(referral.campaign_code, "BOOTH_VISIT_EVENT")
        self.assertEqual(len(issued), 1)
        self.assertEqual((issued[0].benefit_snapshot or {}).get("subtitle"), "[🎁 부스 방문 쿠폰 🎁]")

    def test_booth_visit_code_duplicate_rejected(self):
        referee = self.user_model.objects.create_user(kakao_id=80002, password="pass")
        mock_issued = [MagicMock(code="B001", restaurant_id=101, benefit_snapshot={"subtitle": "[🎁 부스 방문 쿠폰 🎁]"})]
        with patch("coupons.service.issue_booth_visit_coupon", return_value={"coupons": mock_issued, "total_issued": 1, "already_issued": False}):
            accept_referral(referee=referee, ref_code="80THANNIVERSARY")
        ct = CouponType.objects.get(code="FULL_AFFILIATE_SPECIAL")
        camp = Campaign.objects.get(code="BOOTH_VISIT_EVENT")
        Coupon.objects.create(
            code="BOOTHVISDUP1",
            user=referee,
            coupon_type=ct,
            campaign=camp,
            restaurant_id=101,
            expires_at=timezone.now() + timedelta(days=7),
            issue_key=f"EVENT_REWARD:{referee.id}:80THANNIVERSARY:101:0",
            benefit_snapshot={"subtitle": "[🎁 부스 방문 쿠폰 🎁]"},
        )
        with self.assertRaises(ValidationError) as ctx:
            accept_referral(referee=referee, ref_code="80THANNIVERSARY")
        self.assertEqual(ctx.exception.code, "booth_visit_already_issued")


class RouletteCouponTests(TestCase):
    """룰렛 추천코드: 제휴 매장 쿠폰 랜덤 N개 발급."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_model = get_user_model()
        from coupons import signals as coupon_signals
        post_save.disconnect(coupon_signals.on_user_created, sender=cls.user_model)
        cls.addClassCleanup(post_save.connect, coupon_signals.on_user_created, sender=cls.user_model)

    def test_roulette_minyeol_issues_one_coupon_and_sets_subtitle(self):
        referee = self.user_model.objects.create_user(kakao_id=81001, password="pass")
        mock_issued = [MagicMock(code="R001", restaurant_id=101, benefit_snapshot={"subtitle": "[🎰 룰렛 이벤트 쿠폰 🎰]"})]
        with patch("coupons.service.issue_roulette_coupons", return_value={"coupons": mock_issued, "total_issued": 1, "already_issued": False}):
            referral, issued = accept_referral(referee=referee, ref_code="MINYEOL")
        self.assertEqual(referral.campaign_code, "ROULETTE_MINYEOL_EVENT")
        self.assertEqual(len(issued), 1)
        self.assertEqual((issued[0].benefit_snapshot or {}).get("subtitle"), "[🎰 룰렛 이벤트 쿠폰 🎰]")

    def test_roulette_eunjin_issues_five_coupons(self):
        referee = self.user_model.objects.create_user(kakao_id=81002, password="pass")
        mock_issued = [MagicMock(code=f"R{idx:03d}", restaurant_id=100 + idx, benefit_snapshot={"subtitle": "[🎰 룰렛 이벤트 쿠폰 🎰]"}) for idx in range(1, 6)]
        with patch("coupons.service.issue_roulette_coupons", return_value={"coupons": mock_issued, "total_issued": 5, "already_issued": False}):
            referral, issued = accept_referral(referee=referee, ref_code="EUNJIN")
        self.assertEqual(referral.campaign_code, "ROULETTE_EUNJIN_EVENT")
        self.assertEqual(len(issued), 5)

    def test_roulette_jaemin_issues_ten_coupons(self):
        referee = self.user_model.objects.create_user(kakao_id=81003, password="pass")
        mock_issued = [MagicMock(code=f"R{idx:03d}", restaurant_id=100 + idx, benefit_snapshot={"subtitle": "[🎰 룰렛 이벤트 쿠폰 🎰]"}) for idx in range(1, 11)]
        with patch("coupons.service.issue_roulette_coupons", return_value={"coupons": mock_issued, "total_issued": 10, "already_issued": False}):
            referral, issued = accept_referral(referee=referee, ref_code="JAEMIN")
        self.assertEqual(referral.campaign_code, "ROULETTE_JAEMIN_EVENT")
        self.assertEqual(len(issued), 10)

    def test_roulette_chaerin_issues_thirty_coupons(self):
        referee = self.user_model.objects.create_user(kakao_id=81004, password="pass")
        mock_issued = [MagicMock(code=f"R{idx:03d}", restaurant_id=100 + idx, benefit_snapshot={"subtitle": "[🎰 룰렛 이벤트 쿠폰 🎰]"}) for idx in range(1, 31)]
        with patch("coupons.service.issue_roulette_coupons", return_value={"coupons": mock_issued, "total_issued": 30, "already_issued": False}):
            referral, issued = accept_referral(referee=referee, ref_code="CHAERIN")
        self.assertEqual(referral.campaign_code, "ROULETTE_CHAERIN_EVENT")
        self.assertEqual(len(issued), 30)

    def test_roulette_duplicate_rejected(self):
        referee = self.user_model.objects.create_user(kakao_id=81005, password="pass")
        mock_issued = [MagicMock(code="R001", restaurant_id=101, benefit_snapshot={"subtitle": "[🎰 룰렛 이벤트 쿠폰 🎰]"})]
        with patch("coupons.service.issue_roulette_coupons", return_value={"coupons": mock_issued, "total_issued": 1, "already_issued": False}):
            accept_referral(referee=referee, ref_code="MINYEOL")
        ct = CouponType.objects.get(code="FULL_AFFILIATE_SPECIAL")
        camp = Campaign.objects.get(code="ROULETTE_MINYEOL_EVENT")
        Coupon.objects.create(
            code="ROULDUP0001",
            user=referee,
            coupon_type=ct,
            campaign=camp,
            restaurant_id=101,
            expires_at=timezone.now() + timedelta(days=7),
            issue_key=f"EVENT_REWARD:{referee.id}:MINYEOL:101:0",
            benefit_snapshot={"subtitle": "[🎰 룰렛 이벤트 쿠폰 🎰]"},
        )
        with self.assertRaises(ValidationError) as ctx:
            accept_referral(referee=referee, ref_code="MINYEOL")
        self.assertEqual(ctx.exception.code, "roulette_already_issued")


class MediumRareCouponTests(TestCase):
    """미디움레어 추천코드: 하루 최대 4회, 코드 1회성."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_model = get_user_model()
        from coupons import signals as coupon_signals
        post_save.disconnect(coupon_signals.on_user_created, sender=cls.user_model)
        cls.addClassCleanup(post_save.connect, coupon_signals.on_user_created, sender=cls.user_model)

    def test_medium_rare_issues_expected_count_and_subtitle(self):
        referee = self.user_model.objects.create_user(kakao_id=82001, password="pass")
        mock_issued = [MagicMock(code="M001", restaurant_id=101, benefit_snapshot={"subtitle": "[미디움레어 쿠폰 🥩]"})]
        with patch("coupons.service.issue_medium_rare_coupons", return_value={"coupons": mock_issued, "total_issued": 1}):
            referral, issued = accept_referral(referee=referee, ref_code="BRAVENIX")
        self.assertTrue((referral.campaign_code or "").startswith("MEDIUM_RARE:"))
        self.assertEqual(len(issued), 1)
        self.assertEqual((issued[0].benefit_snapshot or {}).get("subtitle"), "[미디움레어 쿠폰 🥩]")

    def test_medium_rare_code_duplicate_rejected(self):
        referee = self.user_model.objects.create_user(kakao_id=82002, password="pass")
        mock_issued = [MagicMock(code="M001", restaurant_id=101, benefit_snapshot={"subtitle": "[미디움레어 쿠폰 🥩]"})]
        with patch("coupons.service.issue_medium_rare_coupons", return_value={"coupons": mock_issued, "total_issued": 1}):
            accept_referral(referee=referee, ref_code="BRAVENIX")
        ct = CouponType.objects.get(code="FULL_AFFILIATE_SPECIAL")
        camp = Campaign.objects.get(code="MEDIUM_RARE_EVENT")
        Coupon.objects.create(
            code="MEDRAREDUP1",
            user=referee,
            coupon_type=ct,
            campaign=camp,
            restaurant_id=101,
            expires_at=timezone.now() + timedelta(days=7),
            issue_key=f"MEDIUM_RARE:{referee.id}:BRAVENIX:101:0",
            benefit_snapshot={"subtitle": "[미디움레어 쿠폰 🥩]"},
        )
        with self.assertRaises(ValidationError) as ctx:
            accept_referral(referee=referee, ref_code="BRAVENIX")
        self.assertEqual(ctx.exception.code, "medium_rare_code_already_used")

    def test_medium_rare_daily_limit_four(self):
        referee = self.user_model.objects.create_user(kakao_id=82003, password="pass")
        # 4회 성공
        with patch("coupons.service.issue_medium_rare_coupons", return_value={"coupons": [MagicMock(code="M001")], "total_issued": 1}):
            accept_referral(referee=referee, ref_code="BRAVENIX")
            accept_referral(referee=referee, ref_code="LOPATERN")
            accept_referral(referee=referee, ref_code="ZEMQUARK")
            accept_referral(referee=referee, ref_code="TOLVAREN")
        # 5번째는 제한
        with self.assertRaises(ValidationError) as ctx:
            with patch("coupons.service.issue_medium_rare_coupons", return_value={"coupons": [MagicMock(code="M002")], "total_issued": 1}):
                accept_referral(referee=referee, ref_code="MEXILORD")
        self.assertEqual(ctx.exception.code, "medium_rare_daily_limit_reached")


class MidtermStudylikeCouponTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_model = get_user_model()
        from coupons import signals as coupon_signals
        post_save.disconnect(coupon_signals.on_user_created, sender=cls.user_model)
        cls.addClassCleanup(post_save.connect, coupon_signals.on_user_created, sender=cls.user_model)

    def test_studylike_issues_three_random_coupons_from_pool(self):
        user = self.user_model.objects.create_user(kakao_id=93001, password="pass")
        ct, _ = CouponType.objects.get_or_create(
            code="MIDTERM_EVENT_SPECIAL",
            defaults={"title": "[중간고사 기획전 쿠폰]", "benefit_json": {}, "valid_days": 0, "per_user_limit": 1},
        )
        camp, _ = Campaign.objects.get_or_create(
            code="MIDTERM_EVENT_STUDYLIKE",
            defaults={"name": "중간고사 기획전 STUDYLIKE 쿠폰", "type": "FLASH", "active": True},
        )

        # 13종 풀 구성
        base_rid = 990000
        for i in range(13):
            RestaurantCouponBenefit.objects.create(
                coupon_type=ct,
                restaurant_id=base_rid + i,
                sort_order=0,
                title=f"혜택{i}",
                subtitle="",
                benefit_json={},
                active=True,
            )

        benefits = list(
            RestaurantCouponBenefit.objects.filter(coupon_type=ct, active=True).order_by("restaurant_id", "sort_order")
        )
        with patch("coupons.service.random.sample", side_effect=lambda seq, k: benefits[:k]):
            result = claim_midterm_studylike_coupon(user, "studylike")

        self.assertFalse(result["already_issued"])
        self.assertEqual(result["total_issued"], 3)
        self.assertEqual(len(result["coupons"]), 3)
        self.assertEqual(len({c.restaurant_id for c in result["coupons"]}), 3)
        for c in result["coupons"]:
            self.assertEqual(c.coupon_type_id, ct.id)
            self.assertEqual(c.campaign_id, camp.id)
            self.assertEqual(c.expires_at, MIDTERM_EVENT_COUPON_EXPIRES_AT)
            self.assertEqual((c.benefit_snapshot or {}).get("subtitle"), "[학생회 한정 쿠폰 📚]")

        # 사용자당 1회성
        result2 = claim_midterm_studylike_coupon(user, "STUDYLIKE")
        self.assertTrue(result2["already_issued"])
        self.assertEqual(result2["total_issued"], 3)

    def test_studylike_after_period_returns_expired(self):
        user = self.user_model.objects.create_user(kakao_id=93002, password="pass")
        CouponType.objects.get_or_create(
            code="MIDTERM_EVENT_SPECIAL",
            defaults={"title": "[중간고사 기획전 쿠폰]", "benefit_json": {}, "valid_days": 0, "per_user_limit": 1},
        )
        Campaign.objects.get_or_create(
            code="MIDTERM_EVENT_STUDYLIKE",
            defaults={"name": "중간고사 기획전 STUDYLIKE 쿠폰", "type": "FLASH", "active": True},
        )
        with patch("coupons.service.timezone.now", return_value=MIDTERM_EVENT_COUPON_EXPIRES_AT + timedelta(seconds=1)):
            with self.assertRaises(ValidationError) as ctx:
                claim_midterm_studylike_coupon(user, "STUDYLIKE")
        self.assertIn("expired", str(ctx.exception))
