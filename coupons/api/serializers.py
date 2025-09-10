from rest_framework import serializers
from ..models import Coupon, InviteCode


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = (
            "code",
            "status",
            "issued_at",
            "expires_at",
            "redeemed_at",
            "coupon_type",
            "campaign",
            "restaurant_id",
        )


class InviteCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = InviteCode
        fields = ("code",)
