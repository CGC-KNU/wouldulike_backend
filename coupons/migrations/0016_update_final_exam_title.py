from django.db import migrations


def update_final_exam_title(apps, schema_editor):
    """FINAL_EXAM_SPECIAL 쿠폰 타입의 title을 업데이트합니다."""
    CouponType = apps.get_model("coupons", "CouponType")
    
    try:
        final_exam_type = CouponType.objects.get(code="FINAL_EXAM_SPECIAL")
        if final_exam_type.title != "기말고사 쪽지 이벤트":
            final_exam_type.title = "기말고사 쪽지 이벤트"
            final_exam_type.save(update_fields=["title"])
    except CouponType.DoesNotExist:
        pass


def revert_final_exam_title(apps, schema_editor):
    """FINAL_EXAM_SPECIAL 쿠폰 타입의 title을 원래대로 되돌립니다."""
    CouponType = apps.get_model("coupons", "CouponType")
    
    try:
        final_exam_type = CouponType.objects.get(code="FINAL_EXAM_SPECIAL")
        final_exam_type.title = "기말고사 특별 발급 쿠폰"
        final_exam_type.save(update_fields=["title"])
    except CouponType.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0015_copy_referral_benefits_to_final_exam"),
    ]

    operations = [
        migrations.RunPython(update_final_exam_title, revert_final_exam_title),
    ]

