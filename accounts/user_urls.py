from django.urls import path

from .views import UserMeView, UserFavoritesView, UserFavoriteDeleteView, NicknameAvailabilityView


urlpatterns = [
    path("me/", UserMeView.as_view(), name="user-me"),
    path("nickname-availability", NicknameAvailabilityView.as_view(), name="nickname-availability-no-slash"),
    path("nickname-availability/", NicknameAvailabilityView.as_view(), name="nickname-availability"),
    path("me/favorites", UserFavoritesView.as_view(), name="user-favorites"),
    path("me/favorites/<str:restaurant_id>", UserFavoriteDeleteView.as_view(), name="user-favorite-delete"),
]
