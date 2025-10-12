from guests.models import GuestUser


def _is_empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return stripped in ("", "[]", "{}", "null", "None")
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def merge_guest_data(guest_uuid, user):
    try:
        guest = GuestUser.objects.get(uuid=guest_uuid)
    except GuestUser.DoesNotExist:
        return

    user_update_fields = set()
    guest_update_fields = set()

    def sync_field(field_name):
        guest_has_field = hasattr(guest, field_name)
        guest_value = getattr(guest, field_name, None) if guest_has_field else None
        user_value = getattr(user, field_name, None)

        if not _is_empty(guest_value):
            if guest_value != user_value:
                setattr(user, field_name, guest_value)
                user_update_fields.add(field_name)
        elif guest_has_field and not _is_empty(user_value):
            if guest_value != user_value:
                setattr(guest, field_name, user_value)
                guest_update_fields.add(field_name)

    for field in ("type_code", "favorite_restaurants", "fcm_token"):
        sync_field(field)

    for optional_field in ("preferences", "survey_responses"):
        sync_field(optional_field)

    if user_update_fields:
        user_update_fields.add("updated_at")
        user.save(update_fields=list(user_update_fields))

    if guest.linked_user_id != user.id:
        guest.linked_user = user
        guest_update_fields.add("linked_user")

    if guest_update_fields:
        guest_update_fields.add("updated_at")
        guest.save(update_fields=list(guest_update_fields))
