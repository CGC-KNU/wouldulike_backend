from django.urls import path

from .views import UserMeView, UserFavoritesView, UserFavoriteDeleteView


urlpatterns = [
    path("me/", UserMeView.as_view(), name="user-me"),
    path("me/favorites", UserFavoritesView.as_view(), name="user-favorites"),
    path("me/favorites/<str:restaurant_id>", UserFavoriteDeleteView.as_view(), name="user-favorite-delete"),
]
