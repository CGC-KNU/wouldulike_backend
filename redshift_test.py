# import psycopg2

# # 연결 테스트
# try:
#     conn = psycopg2.connect(
#         dbname='dev',  # 네임스페이스 데이터베이스 이름
#         user='admin',  # Redshift Serverless 사용자 이름
#         password='Redshiftadmin1!',  # 사용자 비밀번호
#         host='default-workgroup.626635447510.ap-northeast-2.redshift-serverless.amazonaws.com',  # 워크그룹 엔드포인트
#         port=5439  # Redshift 기본 포트
#     )
#     print("Connection successful!")
#     conn.close()
# except Exception as e:
#     print(f"Connection failed: {e}")

import psycopg2

try:
    conn = psycopg2.connect(
        dbname='dev',
        user='admin',
        password='Redshiftadmin1!',
        host='default-workgroup.626635447510.ap-northeast-2.redshift-serverless.amazonaws.com',
        port=5439
    )
    cur = conn.cursor()
    cur.execute("SELECT * FROM restaurant_new LIMIT 10;")
    rows = cur.fetchall()
    for row in rows:
        print(row)
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")


# ---------------------------------------------------------
# Django Coupon System Models (skeleton)
# Note: Guarded to avoid issues when running this script.
#       In a real project, move these to apps/coupons/models.py
# ---------------------------------------------------------
try:
    from django.db import models
    from django.utils import timezone
    from django.contrib.auth import get_user_model

    User = get_user_model()

    class Campaign(models.Model):
        TYPE_CHOICES = [
            ('SIGNUP', 'Signup Welcome'),
            ('REFERRAL', 'Referral'),
            ('FLASH', 'Flash Drop'),
        ]
        code = models.CharField(max_length=40, unique=True)
        name = models.CharField(max_length=80)
        type = models.CharField(max_length=20, choices=TYPE_CHOICES)
        active = models.BooleanField(default=True)
        start_at = models.DateTimeField(null=True, blank=True)
        end_at = models.DateTimeField(null=True, blank=True)
        rules_json = models.JSONField(default=dict, blank=True)  # ex) {"quota_daily":500}

        def __str__(self):
            return f"{self.code} - {self.name}"

    class CouponType(models.Model):
        code = models.CharField(max_length=40, unique=True)   # ex) WELCOME_3000
        title = models.CharField(max_length=80)
        benefit_json = models.JSONField(default=dict)         # {"type":"fixed","value":3000}
        valid_days = models.PositiveIntegerField(default=0)
        per_user_limit = models.PositiveIntegerField(default=1)

        def __str__(self):
            return self.code

    class Coupon(models.Model):
        STATUS = [
            ('ISSUED', 'ISSUED'),
            ('REDEEMED', 'REDEEMED'),
            ('EXPIRED', 'EXPIRED'),
            ('CANCELED', 'CANCELED'),
        ]
        code = models.CharField(max_length=20, unique=True)   # short ULID 등
        user = models.ForeignKey(User, on_delete=models.CASCADE)
        coupon_type = models.ForeignKey(CouponType, on_delete=models.PROTECT)
        campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, null=True, blank=True)
        status = models.CharField(max_length=10, choices=STATUS, default='ISSUED')
        issued_at = models.DateTimeField(default=timezone.now)
        expires_at = models.DateTimeField()
        redeemed_at = models.DateTimeField(null=True, blank=True)
        restaurant_id = models.IntegerField(null=True, blank=True)  # 매장 연동 전까지 int로
        issue_key = models.CharField(max_length=120, null=True, blank=True)  # ex) "SIGNUP:<user_id>"

        class Meta:
            constraints = [
                models.UniqueConstraint(
                    fields=['user', 'coupon_type', 'campaign', 'issue_key'],
                    name='uq_coupon_issue_guard',
                )
            ]

        def __str__(self):
            return self.code

    class InviteCode(models.Model):
        user = models.OneToOneField(User, on_delete=models.CASCADE)
        code = models.CharField(max_length=16, unique=True)
        created_at = models.DateTimeField(auto_now_add=True)

        def __str__(self):
            return f"{self.user_id}:{self.code}"

    class Referral(models.Model):
        STATUS = [
            ('PENDING', 'PENDING'),
            ('QUALIFIED', 'QUALIFIED'),
            ('REJECTED', 'REJECTED'),
        ]
        referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_made')
        referee = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referral_from')
        code_used = models.CharField(max_length=16)
        status = models.CharField(max_length=12, choices=STATUS, default='PENDING')
        qualified_at = models.DateTimeField(null=True, blank=True)

        def __str__(self):
            return f"{self.referrer_id}->{self.referee_id} ({self.status})"

except Exception:
    # Keep this file runnable even if Django or settings are not available.
    # In a proper Django app, place these models under apps/coupons/models.py
    pass
