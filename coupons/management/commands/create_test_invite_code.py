import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from coupons.service import ensure_invite_code


class Command(BaseCommand):
    help = "Generate (or fetch) an invite/referral code for a user so you can test the referral flow."

    def add_arguments(self, parser):
        parser.add_argument(
            "--kakao-id",
            type=int,
            help="Use the given kakao_id. A user will be created automatically if it does not exist.",
        )
        parser.add_argument(
            "--type-code",
            type=str,
            help="Optional type_code to assign when creating the user (or update an existing user).",
        )
        parser.add_argument(
            "--no-create",
            action="store_true",
            help="Fail if the specified user does not exist instead of creating one.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        kakao_id = options.get("kakao_id")
        type_code = options.get("type_code")
        no_create = options["no_create"]

        if kakao_id:
            user = User.objects.filter(kakao_id=kakao_id).first()
            created = False
            if not user:
                if no_create:
                    raise CommandError(
                        f"User with kakao_id={kakao_id} does not exist. "
                        "Pass a different kakao_id or drop --no-create."
                    )
                user = User.objects.create(kakao_id=kakao_id, type_code=type_code)
                created = True
        else:
            user, created = self._create_random_user(User, type_code)
            kakao_id = user.kakao_id

        if type_code and user.type_code != type_code:
            user.type_code = type_code
            user.save(update_fields=["type_code"])

        invite = ensure_invite_code(user)

        action = "created" if created else "reused"
        msg = (
            f"[{action}] kakao_id={kakao_id}, user_id={user.id}, "
            f"invite_code={invite.code}"
        )
        self.stdout.write(self.style.SUCCESS(msg))

    def _create_random_user(self, User, type_code):
        """
        Create a user with a random kakao_id that does not collide with existing records.
        """
        for _ in range(32):
            candidate = random.randint(900000000000, 999999999999)
            try:
                user = User.objects.create(kakao_id=candidate, type_code=type_code)
                return user, True
            except IntegrityError:
                continue
        raise CommandError("Could not find a free kakao_id. Please pass --kakao-id explicitly.")
