from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

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
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
