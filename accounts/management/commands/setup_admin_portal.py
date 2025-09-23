from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create admin groups and default admin accounts for the operations portal."

    def add_arguments(self, parser):
        parser.add_argument("--super-kakao-id", type=int, default=9900000001)
        parser.add_argument("--strategy-kakao-id", type=int, default=9900000002)
        parser.add_argument("--planning-kakao-id", type=int, default=9900000003)
        parser.add_argument("--default-password", type=str, default="change-me-now")
        parser.add_argument("--reset-passwords", action="store_true")

    def handle(self, *args, **options):
        user_model = get_user_model()
        password = options["default_password"]
        reset_passwords = options["reset_passwords"]

        strategy_group = self._ensure_group(
            "Strategy Team",
            {
                "coupons": {
                    "models": [
                        "Campaign",
                        "CouponType",
                        "Coupon",
                        "InviteCode",
                        "Referral",
                        "MerchantPin",
                        "StampWallet",
                        "StampEvent",
                    ],
                    "actions": ("view", "add", "change", "delete"),
                },
                "notifications": {
                    "models": ["Notification"],
                    "actions": ("view", "add", "change", "delete"),
                },
            },
        )

        planning_group = self._ensure_group(
            "Planning Team",
            {
                "coupons": {
                    "models": [
                        "Campaign",
                        "CouponType",
                        "Coupon",
                        "InviteCode",
                        "Referral",
                        "MerchantPin",
                        "StampWallet",
                        "StampEvent",
                    ],
                    "actions": ("view", "change"),
                },
                "notifications": {
                    "models": ["Notification"],
                    "actions": ("view", "add", "change"),
                },
                "trends": {
                    "models": ["Trend"],
                    "actions": ("view", "add", "change"),
                },
            },
        )

        super_user = self._ensure_user(
            user_model,
            kakao_id=options["super_kakao_id"],
            password=password,
            reset_password=reset_passwords,
            is_superuser=True,
            is_staff=True,
            groups=[],
        )
        strategy_user = self._ensure_user(
            user_model,
            kakao_id=options["strategy_kakao_id"],
            password=password,
            reset_password=reset_passwords,
            is_superuser=False,
            is_staff=True,
            groups=[strategy_group],
        )
        planning_user = self._ensure_user(
            user_model,
            kakao_id=options["planning_kakao_id"],
            password=password,
            reset_password=reset_passwords,
            is_superuser=False,
            is_staff=True,
            groups=[planning_group],
        )

        self.stdout.write(self.style.SUCCESS("Admin portal setup complete."))
        self.stdout.write(
            "Created/updated accounts: super=%s strategy=%s planning=%s" % (
                super_user.kakao_id,
                strategy_user.kakao_id,
                planning_user.kakao_id,
            )
        )
        self.stdout.write(
            "Default password applied%s. Please rotate immediately." % (
                " (reset)" if reset_passwords else " on new accounts only"
            )
        )

    def _ensure_group(self, name, spec):
        group, _ = Group.objects.get_or_create(name=name)
        permissions = []
        for app_label, entry in spec.items():
            models = entry.get("models", [])
            actions = entry.get("actions", ("view", "change"))
            for model_name in models:
                model = apps.get_model(app_label, model_name)
                if model is None:
                    self.stdout.write(self.style.WARNING(f"Model {app_label}.{model_name} not found"))
                    continue
                for action in actions:
                    codename = f"{action}_{model._meta.model_name}"
                    try:
                        perm = Permission.objects.get(content_type__app_label=app_label, codename=codename)
                        permissions.append(perm)
                    except Permission.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Permission {app_label}.{codename} missing; run migrations before setup."
                            )
                        )
        group.permissions.set(permissions)
        return group

    def _ensure_user(
        self,
        user_model,
        *,
        kakao_id,
        password,
        reset_password,
        is_superuser,
        is_staff,
        groups,
    ):
        user, created = user_model.objects.get_or_create(
            kakao_id=kakao_id,
            defaults={"is_staff": is_staff, "is_superuser": is_superuser},
        )
        changed = False
        if created or reset_password:
            user.set_password(password)
            changed = True
        if user.is_staff != is_staff:
            user.is_staff = is_staff
            changed = True
        if user.is_superuser != is_superuser:
            user.is_superuser = is_superuser
            changed = True
        if groups is not None:
            user.groups.set(groups)
        if changed:
            user.save()
        return user
