from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.db.models.signals import post_save
from django.utils import timezone

from coupons.models import Campaign, Coupon, CouponType, InviteCode, Referral
from coupons.service import accept_referral, issue_signup_coupon, qualify_referral_and_grant, MAX_COUPONS_PER_RESTAURANT, ensure_invite_code


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

    def test_signup_coupon_assigns_available_restaurant(self):
        user = self._create_user(1)
        with patch(
            "coupons.service.Restaurant.objects.values_list",
            side_effect=lambda *args, **kwargs: [101, 102],
        ):
            coupon = issue_signup_coupon(user)
        self.assertIn(coupon.restaurant_id, [101, 102])

    def test_allocation_skips_restaurant_when_limit_reached(self):
        restaurant_ids = [201, 202]
        existing_user = self._create_user(2)
        for idx in range(MAX_COUPONS_PER_RESTAURANT):
            Coupon.objects.create(
                code=f"PRE{idx:04d}",
                user=existing_user,
                coupon_type=self.coupon_type,
                campaign=self.campaign,
                expires_at=timezone.now(),
                restaurant_id=restaurant_ids[0],
                issue_key=f"PRE-{idx}",
            )

        new_user = self._create_user(3)
        with patch(
            "coupons.service.Restaurant.objects.values_list",
            side_effect=lambda *args, **kwargs: list(restaurant_ids),
        ):
            coupon = issue_signup_coupon(new_user)
        self.assertEqual(coupon.restaurant_id, restaurant_ids[1])

    def test_allocation_prefers_least_assigned_restaurant(self):
        restaurant_ids = [301, 302, 303]
        base_user = self._create_user(4)
        for idx, restaurant_id in enumerate([301] * 3 + [302] * 5):
            Coupon.objects.create(
                code=f"BAL{idx:04d}",
                user=base_user,
                coupon_type=self.coupon_type,
                campaign=self.campaign,
                expires_at=timezone.now(),
                restaurant_id=restaurant_id,
                issue_key=f"BAL-{idx}",
            )

        new_user = self._create_user(5)
        with patch(
            "coupons.service.Restaurant.objects.values_list",
            side_effect=lambda *args, **kwargs: list(restaurant_ids),
        ):
            coupon = issue_signup_coupon(new_user)
        self.assertEqual(coupon.restaurant_id, restaurant_ids[2])


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
        self.invite_code = self.referrer.invite_code

    def test_referral_acceptance_capped_at_five(self):
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

    def test_referral_rewards_respect_per_restaurant_limit(self):
        restaurant_ids = [401, 402]
        referrer = self._create_user(1)
        ensure_invite_code(referrer)
        referee = self._create_user(2)
        accept_referral(referee=referee, ref_code=referrer.invite_code.code)
        existing_holder = self._create_user(3)
        now = timezone.now()
        for idx in range(MAX_COUPONS_PER_RESTAURANT):
            Coupon.objects.create(
                code=f"RR{idx:04d}",
                user=existing_holder,
                coupon_type=self.referrer_type,
                campaign=self.campaign,
                expires_at=now,
                restaurant_id=restaurant_ids[0],
                issue_key=f"RR-{idx}",
            )
        for idx in range(MAX_COUPONS_PER_RESTAURANT):
            Coupon.objects.create(
                code=f"RE{idx:04d}",
                user=existing_holder,
                coupon_type=self.referee_type,
                campaign=self.campaign,
                expires_at=now,
                restaurant_id=restaurant_ids[0],
                issue_key=f"RE-{idx}",
            )
        with patch(
            "coupons.service.Restaurant.objects.values_list",
            side_effect=lambda *args, **kwargs: list(restaurant_ids),
        ):
            qualify_referral_and_grant(referee)

        referrer_coupon = (
            Coupon.objects.filter(user=referrer, coupon_type=self.referrer_type)
            .order_by("-issued_at")
            .first()
        )
        referee_coupon = (
            Coupon.objects.filter(user=referee, coupon_type=self.referee_type)
            .order_by("-issued_at")
            .first()
        )

        self.assertIsNotNone(referrer_coupon)
        self.assertIsNotNone(referee_coupon)
        self.assertEqual(referrer_coupon.restaurant_id, restaurant_ids[1])
        self.assertEqual(referee_coupon.restaurant_id, restaurant_ids[1])
