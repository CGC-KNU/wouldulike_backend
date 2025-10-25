from django.urls import path
from .views import (
    MyCouponsView,
    SignupCompleteView,
    RedeemView,
    CheckCouponView,
    MyInviteCodeView,
    AcceptReferralView,
    QualifyReferralView,
    FlashClaimView,
    AddStampView,
    MyAllStampStatusView,
    MyStampStatusView,
)

urlpatterns = [
    path("coupons/my/", MyCouponsView.as_view()),
    path("coupons/signup/complete/", SignupCompleteView.as_view()),
    path("coupons/redeem/", RedeemView.as_view()),
    path("coupons/check/", CheckCouponView.as_view()),
    path("coupons/invite/my/", MyInviteCodeView.as_view()),
    path("coupons/referrals/accept/", AcceptReferralView.as_view()),
    path("coupons/referrals/qualify/", QualifyReferralView.as_view()),
    path("coupons/flash/claim/", FlashClaimView.as_view()),
]

# Stamp endpoints
urlpatterns += [
    path("coupons/stamps/add/", AddStampView.as_view()),
    path("coupons/stamps/my/all/", MyAllStampStatusView.as_view()),
    path("coupons/stamps/my/", MyStampStatusView.as_view()),
]
