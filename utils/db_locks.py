from django.db import connections, router
from django.db.transaction import TransactionManagementError
from django.db.utils import NotSupportedError


def locked_get(queryset, *, using_alias=None, for_update=True, **filters):
    """Fetch a row with optional select_for_update, falling back gracefully."""
    alias = using_alias or router.db_for_read(queryset.model) or "default"
    conn = connections[alias]
    qs = queryset.using(alias)

    if for_update and getattr(conn.features, "has_select_for_update", False):
        try:
            qs = qs.select_for_update()
        except (NotSupportedError, TransactionManagementError):
            pass

    try:
        return qs.get(**filters)
    except (NotSupportedError, TransactionManagementError):
        if for_update:
            fallback_qs = queryset.using(alias)
            return fallback_qs.get(**filters)
        raise
