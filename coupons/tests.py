from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from coupons.models import InviteCode, Referral
from coupons.service import accept_referral


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
