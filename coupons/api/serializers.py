from django.db import router, DatabaseError
from rest_framework import serializers
from restaurants.models import AffiliateRestaurant
from ..models import Coupon, InviteCode


class CouponSerializer(serializers.ModelSerializer):
    coupon_type_code = serializers.CharField(source="coupon_type.code", read_only=True)
    coupon_type_title = serializers.CharField(source="coupon_type.title", read_only=True)
    benefit = serializers.SerializerMethodField()
    restaurant_name = serializers.SerializerMethodField()
    restaurant_category = serializers.SerializerMethodField()

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
            "restaurant_category",
            "benefit",
            "issue_key",
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
            if "restaurant_category" not in snapshot:
                category = self.get_restaurant_category(obj)
                if category:
                    snapshot["restaurant_category"] = category
            return snapshot

        fallback = {
            "coupon_type_code": obj.coupon_type.code,
            "coupon_type_title": correct_coupon_type_title,
            "restaurant_id": obj.restaurant_id,
            "benefit": obj.coupon_type.benefit_json,
            "title": obj.coupon_type.title,
            "subtitle": "",
            "notes": "",
        }
        restaurant_name = self.get_restaurant_name(obj)
        if restaurant_name:
            fallback["restaurant_name"] = restaurant_name
        restaurant_category = self.get_restaurant_category(obj)
        if restaurant_category:
            fallback["restaurant_category"] = restaurant_category
        return fallback

    def get_restaurant_name(self, obj: Coupon):
        snapshot = obj.benefit_snapshot or {}
        snapshot_name = snapshot.get("restaurant_name")
        if snapshot_name:
            return snapshot_name
        name, _ = self._get_restaurant_meta(obj.restaurant_id, None)
        return name

    def get_restaurant_category(self, obj: Coupon):
        snapshot = obj.benefit_snapshot or {}
        snapshot_category = snapshot.get("restaurant_category")
        if snapshot_category:
            return snapshot_category
        snapshot_name = snapshot.get("restaurant_name")
        _, category = self._get_restaurant_meta(obj.restaurant_id, snapshot_name)
        return category

    def _get_restaurant_meta(self, restaurant_id, restaurant_name_hint=None):
        id_cache = self.context.setdefault("_restaurant_meta_cache_by_id", {})
        name_cache = self.context.setdefault("_restaurant_meta_cache_by_name", {})
        alias = router.db_for_read(AffiliateRestaurant)

        if restaurant_id:
            if restaurant_id in id_cache:
                return id_cache[restaurant_id]
            try:
                row = (
                    AffiliateRestaurant.objects.using(alias)
                    .filter(restaurant_id=restaurant_id)
                    .values("name", "category")
                    .first()
                )
                if row:
                    meta = (row.get("name"), row.get("category"))
                    id_cache[restaurant_id] = meta
                    if row.get("name"):
                        name_cache[row["name"]] = meta
                    return meta
            except DatabaseError:
                pass
            id_cache[restaurant_id] = (None, None)

        # 과거 발급분 중 restaurant_id가 비어 있고 restaurant_name만 있는 경우 보정
        if restaurant_name_hint:
            if restaurant_name_hint in name_cache:
                return name_cache[restaurant_name_hint]
            try:
                row = (
                    AffiliateRestaurant.objects.using(alias)
                    .filter(name=restaurant_name_hint)
                    .values("name", "category")
                    .first()
                )
                if row:
                    meta = (row.get("name"), row.get("category"))
                    name_cache[restaurant_name_hint] = meta
                    return meta
            except DatabaseError:
                pass
            name_cache[restaurant_name_hint] = (None, None)

        return (None, None)


class InviteCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = InviteCode
        fields = ("code",)
