from guests.models import GuestUser


def merge_guest_data(guest_uuid, user):
    try:
        guest = GuestUser.objects.get(uuid=guest_uuid)
    except GuestUser.DoesNotExist:
        return

    if guest.type_code and not user.type_code:
        user.type_code = guest.type_code
    if guest.favorite_restaurants and not user.favorite_restaurants:
        user.favorite_restaurants = guest.favorite_restaurants
    if guest.fcm_token and not user.fcm_token:
        user.fcm_token = guest.fcm_token
    user.save()
    guest.delete()