import os

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError

ROLE_CONFIG = {
    "super": {
        "label": "Super Admin",
        "is_superuser": True,
        "is_staff": True,
        "group": None,
    },
    "strategy": {
        "label": "Strategy Admin",
        "is_superuser": False,
        "is_staff": True,
        "group": "Strategy Team",
    },
    "planning": {
        "label": "Planning Admin",
        "is_superuser": False,
        "is_staff": True,
        "group": "Planning Team",
    },
}

GROUP_SPECS = {
    "Strategy Team": {
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
    "Planning Team": {
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
}

ROLE_ORDER = ("super", "strategy", "planning")


class Command(BaseCommand):
    help = "Create admin groups and default admin accounts for the operations portal."

    def add_arguments(self, parser):
        parser.add_argument("--accounts-env-var", default="OPERATIONS_ADMIN_ACCOUNTS")
        parser.add_argument("--default-password", type=str, default="change-me-now")
        parser.add_argument("--super-kakao-id", type=int, default=9900000001)
        parser.add_argument("--strategy-kakao-id", type=int, default=9900000002)
        parser.add_argument("--planning-kakao-id", type=int, default=9900000003)
        parser.add_argument("--reset-passwords", action="store_true")

    def handle(self, *args, **options):
        env_var_name = options["accounts_env_var"]
        default_password = self._resolve_default_password(options)
        reset_passwords = self._resolve_reset_passwords(options)

        accounts = self._load_accounts(options, env_var_name)
        if not accounts:
            raise CommandError(
                "No admin accounts configured. Set the %s environment variable or provide CLI options." % env_var_name
            )

        user_model = get_user_model()
        groups_by_name = self._ensure_groups()

        summary = []
        for role in ROLE_ORDER:
            account = accounts.get(role)
            if account is None:
                self.stdout.write(self.style.WARNING(f"No account configuration found for role '{role}'. Skipping."))
                continue

            config = ROLE_CONFIG[role]
            password = account.get("password") or default_password
            used_default_password = account.get("password") in (None, "")

            if not password:
                raise CommandError(
                    f"Unable to provision the {config['label']} account; no password supplied in env or defaults."
                )

            reset_flag = account.get("reset_password")
            if reset_flag is None:
                reset_flag = reset_passwords
            else:
                reset_flag = bool(reset_flag)

            group_name = config["group"]
            group_objects = []
            if group_name:
                group_objects = [groups_by_name[group_name]]

            user = self._ensure_user(
                user_model,
                kakao_id=account["kakao_id"],
                password=password,
                reset_password=reset_flag,
                is_superuser=config["is_superuser"],
                is_staff=config["is_staff"],
                groups=group_objects,
            )

            summary.append(
                {
                    "role": role,
                    "label": config["label"],
                    "user": user,
                    "reset": reset_flag,
                    "used_default_password": used_default_password,
                }
            )

        if not summary:
            raise CommandError("No accounts were created or updated. Check your configuration and try again.")

        self.stdout.write(self.style.SUCCESS("Admin portal setup complete."))
        for entry in summary:
            role = entry["role"]
            label = entry["label"]
            user = entry["user"]
            reset = entry["reset"]
            used_default = entry["used_default_password"]
            group_name = ROLE_CONFIG[role]["group"]
            group_display = group_name if group_name else "(none)"
            reset_msg = "reset" if reset else "preserved"
            self.stdout.write(
                f" - {label}: kakao_id={user.kakao_id} groups={group_display} password={reset_msg}"
            )
            if used_default:
                self.stdout.write(
                    self.style.WARNING(
                        f"   Password sourced from default value '{default_password}'. Update OPERATIONS_ADMIN_ACCOUNTS to set an explicit password."
                    )
                )

    def _ensure_groups(self):
        groups = {}
        for name, spec in GROUP_SPECS.items():
            groups[name] = self._ensure_group(name, spec)
        return groups

    def _load_accounts(self, options, env_var_name):
        accounts = {}
        env_value = os.environ.get(env_var_name)
        if env_value:
            accounts.update(self._parse_accounts_env(env_value, env_var_name))
        fallback = self._accounts_from_options(options)
        for role, entry in fallback.items():
            accounts.setdefault(role, entry)
        return accounts

    def _resolve_default_password(self, options):
        env_password = os.environ.get("OPERATIONS_ADMIN_DEFAULT_PASSWORD")
        if env_password:
            return env_password
        return options.get("default_password")

    def _resolve_reset_passwords(self, options):
        env_flag = os.environ.get("OPERATIONS_ADMIN_RESET_PASSWORDS")
        if env_flag is not None:
            return self._env_str_to_bool(env_flag)
        return options.get("reset_passwords", False)

    def _accounts_from_options(self, options):
        accounts = {}
        mapping = {
            "super": options.get("super_kakao_id"),
            "strategy": options.get("strategy_kakao_id"),
            "planning": options.get("planning_kakao_id"),
        }
        for role, kakao_id in mapping.items():
            if kakao_id is None:
                continue
            accounts[role] = {"kakao_id": kakao_id, "password": None, "reset_password": None}
        return accounts

    def _parse_accounts_env(self, raw, env_var_name):
        accounts = {}
        for chunk in raw.split(";"):
            value = chunk.strip()
            if not value:
                continue
            parts = [part.strip() for part in value.split(":")]
            if len(parts) < 3:
                raise CommandError(
                    f"Invalid entry '{value}' in {env_var_name}. Expected format ROLE:KAKAO_ID:PASSWORD[:RESET]."
                )
            role = parts[0].lower()
            if role not in ROLE_CONFIG:
                raise CommandError(
                    f"Unknown role '{role}' in {env_var_name}. Supported roles: {', '.join(ROLE_ORDER)}."
                )
            if role in accounts:
                raise CommandError(f"Duplicate entry for role '{role}' in {env_var_name}.")
            try:
                kakao_id = int(parts[1])
            except ValueError as exc:
                raise CommandError(f"Invalid kakao_id '{parts[1]}' for role '{role}'.") from exc
            password = parts[2]
            reset_value = parts[3] if len(parts) >= 4 else None
            entry = {"kakao_id": kakao_id, "password": password}
            if reset_value is not None:
                entry["reset_password"] = self._env_str_to_bool(reset_value)
            else:
                entry["reset_password"] = None
            accounts[role] = entry
        return accounts

    def _env_str_to_bool(self, value):
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

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
