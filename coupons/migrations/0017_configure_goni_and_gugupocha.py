from django.db import migrations


def configure_goni_and_gugupocha(apps, schema_editor):
    """
    고니식탁과 구구포차 쿠폰 설정:
    1. 고니식탁(restaurant_id 30)은 친구초대, 기말고사 이벤트 시 쿠폰 발급 불가 (이미 COUPON_TYPE_EXCLUDED_RESTAURANTS에 설정됨)
    2. 구구포차는 신규가입, 친구초대, 기말고사 이벤트 시 "살얼음 생맥주 500cc/하이볼/주류 택 1" 쿠폰 발급
    """
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")
    
    # 구구포차 쿠폰 내용 설정
    coupon_types = [
        "WELCOME_3000",  # 신규가입
        "REFERRAL_BONUS_REFEREE",  # 친구초대 (피추천인)
        "FINAL_EXAM_SPECIAL",  # 기말고사 이벤트
    ]
    
    # 구구포차 쿠폰 내용
    gugupocha_benefit = {
        "title": "살얼음 생맥주 500cc/하이볼/주류 택 1",
        "subtitle": "",
        "benefit_json": {"type": "fixed", "value": 0},  # 실제 혜택은 식당에서 처리
        "active": True,
    }
    
    # 구구포차의 restaurant_id를 찾기 위한 로직
    AffiliateRestaurant = apps.get_model("restaurants", "AffiliateRestaurant")
    
    try:
        # 구구포차 찾기 (이름에 "구구"가 포함된 식당)
        # 여러 DB에서 시도
        gugupocha_restaurants = None
        
        # default DB에서 시도
        try:
            gugupocha_restaurants = AffiliateRestaurant.objects.filter(
                name__icontains='구구'
            )
            if not gugupocha_restaurants.exists():
                gugupocha_restaurants = None
        except Exception:
            pass
        
        # CloudSQL에서 시도
        if not gugupocha_restaurants:
            try:
                gugupocha_restaurants = AffiliateRestaurant.objects.using('cloudsql').filter(
                    name__icontains='구구'
                )
            except Exception:
                pass
        
        if gugupocha_restaurants:
            for gugupocha in gugupocha_restaurants:
                restaurant_id = gugupocha.restaurant_id
                
                # 각 쿠폰 타입에 대해 구구포차 쿠폰 내용 설정
                for coupon_type_code in coupon_types:
                    try:
                        coupon_type = CouponType.objects.get(code=coupon_type_code)
                        
                        # RestaurantCouponBenefit를 생성하여 쿠폰 내용 설정
                        RestaurantCouponBenefit.objects.update_or_create(
                            coupon_type=coupon_type,
                            restaurant_id=restaurant_id,
                            defaults=gugupocha_benefit,
                        )
                    except CouponType.DoesNotExist:
                        continue
    
    except Exception:
        # 에러가 발생해도 마이그레이션은 계속 진행
        # 구구포차를 찾지 못했거나 다른 문제가 있을 수 있음
        pass


def revert_goni_and_gugupocha(apps, schema_editor):
    """구구포차 쿠폰 내용 설정을 되돌립니다."""
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")
    
    coupon_types = [
        "WELCOME_3000",
        "REFERRAL_BONUS_REFEREE",
        "FINAL_EXAM_SPECIAL",
    ]
    
    AffiliateRestaurant = apps.get_model("restaurants", "AffiliateRestaurant")
    
    try:
        # 여러 DB에서 시도
        gugupocha_restaurants = None
        
        try:
            gugupocha_restaurants = AffiliateRestaurant.objects.filter(
                name__icontains='구구'
            )
            if not gugupocha_restaurants.exists():
                gugupocha_restaurants = None
        except Exception:
            pass
        
        if not gugupocha_restaurants:
            try:
                gugupocha_restaurants = AffiliateRestaurant.objects.using('cloudsql').filter(
                    name__icontains='구구'
                )
            except Exception:
                pass
        
        if gugupocha_restaurants:
            for gugupocha in gugupocha_restaurants:
                restaurant_id = gugupocha.restaurant_id
                
                for coupon_type_code in coupon_types:
                    try:
                        coupon_type = CouponType.objects.get(code=coupon_type_code)
                        RestaurantCouponBenefit.objects.filter(
                            coupon_type=coupon_type,
                            restaurant_id=restaurant_id,
                        ).delete()
                    except CouponType.DoesNotExist:
                        continue
    except Exception:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0016_update_final_exam_title"),
    ]

    operations = [
        migrations.RunPython(configure_goni_and_gugupocha, revert_goni_and_gugupocha),
    ]

