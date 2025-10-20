from django.contrib import admin
from .models import (
    Campaign,
    CouponType,
    Coupon,
    InviteCode,
    Referral,
    MerchantPin,
    StampWallet,
    StampEvent,
    RestaurantCouponBenefit,
)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "type", "active", "start_at", "end_at")
    list_filter = ("type", "active")
    search_fields = ("code", "name")


@admin.register(CouponType)
class CouponTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "valid_days", "per_user_limit")
    search_fields = ("code", "title")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "user",
        "coupon_type",
        "campaign",
        "status",
        "issued_at",
        "expires_at",
        "redeemed_at",
    )
    list_filter = ("status", "coupon_type", "campaign")
    search_fields = ("code", "user__kakao_id")


@admin.register(RestaurantCouponBenefit)
class RestaurantCouponBenefitAdmin(admin.ModelAdmin):
    list_display = (
        "coupon_type",
        "restaurant_id",
        "restaurant_name",
        "title",
        "active",
        "updated_at",
    )
    list_filter = ("coupon_type", "active")
    search_fields = (
        "coupon_type__code",
        "coupon_type__title",
        "restaurant__name",
        "restaurant_id",
        "title",
    )
    raw_id_fields = ("coupon_type", "restaurant")

    @staticmethod
    def restaurant_name(obj):
        return getattr(obj.restaurant, "name", "-")


@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "code", "created_at")
    search_fields = ("code", "user__kakao_id")


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ("referrer", "referee", "code_used", "status", "qualified_at")
    list_filter = ("status",)
    search_fields = (
        "code_used",
        "referrer__kakao_id",
        "referee__kakao_id",
    )


@admin.register(MerchantPin)
class MerchantPinAdmin(admin.ModelAdmin):
    list_display = ("restaurant_id", "restaurant_name", "algo", "last_rotated_at")
    list_filter = ("algo",)
    search_fields = ("restaurant_id", "restaurant__name")

    @staticmethod
    def restaurant_name(obj):
        return getattr(obj.restaurant, 'name', '-')


@admin.register(StampWallet)
class StampWalletAdmin(admin.ModelAdmin):
    list_display = ("user", "restaurant_id", "stamps", "updated_at")
    search_fields = ("user__kakao_id", "restaurant_id")


@admin.register(StampEvent)
class StampEventAdmin(admin.ModelAdmin):
    list_display = ("user", "restaurant_id", "delta", "source", "created_at")
    list_filter = ("source",)
    search_fields = ("user__kakao_id", "restaurant_id")
