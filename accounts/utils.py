from guests.models import GuestUser


def merge_guest_data(guest_uuid, user):
    try:
        guest = GuestUser.objects.get(uuid=guest_uuid)
    except GuestUser.DoesNotExist:
        return

    updated_fields = []

    if guest.type_code and guest.type_code != user.type_code:
        user.type_code = guest.type_code
        updated_fields.append("type_code")

    guest_favorites = getattr(guest, "favorite_restaurants", None)
    if guest_favorites and guest_favorites != user.favorite_restaurants:
        user.favorite_restaurants = guest_favorites
        updated_fields.append("favorite_restaurants")

    if guest.fcm_token and guest.fcm_token != user.fcm_token:
        user.fcm_token = guest.fcm_token
        updated_fields.append("fcm_token")

    for attr in ("preferences", "survey_responses"):
        if hasattr(guest, attr):
            value = getattr(guest, attr)
            if value and value != getattr(user, attr, None):
                setattr(user, attr, value)
                updated_fields.append(attr)

    if updated_fields:
        update_fields = set(updated_fields)
        update_fields.add("updated_at")
        user.save(update_fields=list(update_fields))

    guest.delete()
