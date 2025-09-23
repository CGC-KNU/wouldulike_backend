from django.contrib import admin
from django.urls import path, include
admin.site.site_header = "WouldULike Operations Admin"
admin.site.site_title = "WouldULike Admin Portal"
admin.site.index_title = "Data Operations Dashboard"

from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from accounts.views import DevLoginView  # dev-only helper
from rest_framework_simplejwt.views import TokenRefreshView
from coupons.api.views import (
    AddStampView,
    MyStampStatusView,
    MyCouponsView,
    SignupCompleteView,
    RedeemView,
    CheckCouponView,
    MyInviteCodeView,
    AcceptReferralView,
    QualifyReferralView,
    FlashClaimView,
)

def home_view(request):
    return HttpResponse("<h1>WouldULike</h1>")

urlpatterns = [
    path('', home_view, name='home'),
    path('admin/', admin.site.urls),
    path('guests/', include('guests.urls')),
    path('trends/', include('trends.urls')),
    path('type-descriptions/', include('type_description.urls')),
    path('food-by-type/', include('food_by_type.urls')),
    path('restaurants/', include('restaurants.urls')),
    path('notifications/', include('notifications.urls')),
    path('api/auth/', include('accounts.urls')),
    path('api/', include('coupons.api.urls')),
    # Alias for dev login requested as /auth/dev-login/
    path('auth/dev-login/', DevLoginView.as_view()),
    # Auth aliases (avoid CSRF by ensuring DRF view is hit even without /api prefix)
    path('auth/refresh/', TokenRefreshView.as_view(), name='alias-token-refresh'),
    # Backward-compat alias: allow calling /coupons/stamps/add/ without the /api prefix
    path('coupons/stamps/add/', AddStampView.as_view()),
    # Backward-compat alias: allow calling /coupons/stamps/my/ without the /api prefix
    path('coupons/stamps/my/', MyStampStatusView.as_view()),
    # Other coupon API aliases without /api prefix
    path('coupons/my/', MyCouponsView.as_view()),
    path('coupons/signup/complete/', SignupCompleteView.as_view()),
    path('coupons/redeem/', RedeemView.as_view()),
    path('coupons/check/', CheckCouponView.as_view()),
    path('coupons/invite/my/', MyInviteCodeView.as_view()),
    path('coupons/referrals/accept/', AcceptReferralView.as_view()),
    path('coupons/referrals/qualify/', QualifyReferralView.as_view()),
    path('coupons/flash/claim/', FlashClaimView.as_view()),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
