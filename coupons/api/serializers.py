from django.db import router, DatabaseError
from rest_framework import serializers
from restaurants.models import AffiliateRestaurant
from ..models import Coupon, InviteCode


class CouponSerializer(serializers.ModelSerializer):
    coupon_type_code = serializers.CharField(source="coupon_type.code", read_only=True)
    coupon_type_title = serializers.CharField(source="coupon_type.title", read_only=True)
    benefit = serializers.SerializerMethodField()
    restaurant_name = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = (
            "code",
            "status",
            "issued_at",
            "expires_at",
            "redeemed_at",
            "coupon_type",
            "coupon_type_code",
            "coupon_type_title",
            "campaign",
            "restaurant_id",
            "restaurant_name",
            "benefit",
        )

    def get_benefit(self, obj: Coupon):
        snapshot = obj.benefit_snapshot or {}
        
        # coupon_type_title은 항상 CouponType.title을 사용 (benefit_snapshot과 무관하게)
        # 프론트엔드가 benefit.coupon_type_title을 사용하더라도 올바른 값이 전달되도록 보장
        correct_coupon_type_title = obj.coupon_type.title
        
        if snapshot:
            # benefit_snapshot이 있으면 사용하되, coupon_type_title은 항상 올바른 값으로 덮어쓰기
            snapshot = snapshot.copy()  # 원본 수정 방지
            snapshot["coupon_type_title"] = correct_coupon_type_title
            return snapshot

        fallback = {
            "coupon_type_code": obj.coupon_type.code,
            "coupon_type_title": correct_coupon_type_title,
            "restaurant_id": obj.restaurant_id,
            "benefit": obj.coupon_type.benefit_json,
            "title": obj.coupon_type.title,
            "subtitle": "",
        }
        restaurant_name = self.get_restaurant_name(obj)
        if restaurant_name:
            fallback["restaurant_name"] = restaurant_name
        return fallback

    def get_restaurant_name(self, obj: Coupon):
        snapshot = obj.benefit_snapshot or {}
        name = snapshot.get("restaurant_name")
        if name:
            return name

        restaurant_id = obj.restaurant_id
        if not restaurant_id:
            return None

        cache = self.context.setdefault("_restaurant_name_cache", {})
        if restaurant_id in cache:
            return cache[restaurant_id]

        alias = router.db_for_read(AffiliateRestaurant)
        try:
            fetched = (
                AffiliateRestaurant.objects.using(alias)
                .filter(restaurant_id=restaurant_id)
                .values_list("name", flat=True)
                .first()
            )
        except DatabaseError:
            fetched = None
        cache[restaurant_id] = fetched
        return fetched


class InviteCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = InviteCode
        fields = ("code",)
