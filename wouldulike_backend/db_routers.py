from django.conf import settings


class TypeDescriptionRouter:
    @staticmethod
    def _use_cloudsql_unified() -> bool:
        return getattr(settings, "USE_CLOUDSQL_UNIFIED", False)

    def db_for_read(self, model, **hints):
        """Choose the database for read operations."""
        if self._use_cloudsql_unified():
            return "default"

        instance = hints.get("instance")
        if (
            instance is not None
            and getattr(instance._meta, "app_label", None) == "coupons"
            and getattr(model._meta, "app_label", None) == "accounts"
        ):
            return "default"
        if model._meta.app_label in {"type_description", "food_by_type"}:
            return "cloudsql"
        if model._meta.app_label in {
            "coupons",
            "campus_restaurants",
            "restaurants",
            "trends",
        }:
            return "cloudsql"
        return "default"

    def db_for_write(self, model, **hints):
        """Choose the database for write operations."""
        if self._use_cloudsql_unified():
            return "default"

        instance = hints.get("instance")
        if (
            instance is not None
            and getattr(instance._meta, "app_label", None) == "coupons"
            and getattr(model._meta, "app_label", None) == "accounts"
        ):
            return "default"
        if model._meta.app_label in {"type_description", "food_by_type"}:
            return "cloudsql"
        if model._meta.app_label in {
            "coupons",
            "campus_restaurants",
            "restaurants",
            "trends",
        }:
            return "cloudsql"
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations between objects from any database."""
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Control where migrations run for each app."""
        if self._use_cloudsql_unified():
            if app_label == "campus_restaurants":
                return False
            return db == "default"

        if app_label in {"type_description", "food_by_type"}:
            return db in {"cloudsql", "rds"}
        if app_label in {"coupons", "trends", "restaurants"}:
            return db == "cloudsql"
        if app_label == "campus_restaurants":
            return False
        return db == "default"
