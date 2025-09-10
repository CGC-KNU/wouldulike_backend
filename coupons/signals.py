from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .service import issue_signup_coupon, ensure_invite_code


User = get_user_model()


@receiver(post_save, sender=User)
def on_user_created(sender, instance, created, **kwargs):
    if not created:
        return
    ensure_invite_code(instance)
    try:
        issue_signup_coupon(instance)
    except Exception:
        # Unique 제약으로 이미 발급된 경우 등은 무시
        pass
