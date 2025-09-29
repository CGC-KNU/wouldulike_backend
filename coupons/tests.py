from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from coupons.models import Campaign, Coupon, CouponType, InviteCode, Referral
from coupons.service import accept_referral, issue_signup_coupon


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
        for idx in range(200):
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
    def setUp(self):
        self.user_model = get_user_model()
        self.referrer = self.user_model.objects.create_user(kakao_id=1000, password="pass")
        self.invite_code = self.referrer.invite_code

    def test_referral_acceptance_capped_at_five(self):
        for idx in range(5):
            referee = self.user_model.objects.create_user(kakao_id=2000 + idx, password="pass")
            referral = accept_referral(referee=referee, ref_code=self.invite_code.code)
            self.assertEqual(referral.referrer, self.referrer)

        self.assertEqual(Referral.objects.filter(referrer=self.referrer).count(), 5)

        sixth_referee = self.user_model.objects.create_user(kakao_id=3000, password="pass")
        with self.assertRaises(ValidationError) as ctx:
            accept_referral(referee=sixth_referee, ref_code=self.invite_code.code)

        self.assertEqual(ctx.exception.code, "referral_limit_reached")
        self.assertEqual(Referral.objects.filter(referrer=self.referrer).count(), 5)
