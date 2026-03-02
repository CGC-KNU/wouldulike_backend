from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser, PermissionsMixin, BaseUserManager
)


class UserManager(BaseUserManager):
    def create_user(self, kakao_id=None, apple_id=None, password=None, **extra_fields):
        if kakao_id is None and apple_id is None:
            raise ValueError('Users must have either kakao_id or apple_id')
        if kakao_id is not None:
            username = str(kakao_id)
        else:
            username = f"apple_{apple_id}"
        user = self.model(
            kakao_id=kakao_id,
            apple_id=apple_id,
            username=username,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, kakao_id, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(kakao_id=kakao_id, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=255, unique=True, db_index=True)
    kakao_id = models.BigIntegerField(unique=True, db_index=True, null=True, blank=True)
    apple_id = models.CharField(max_length=255, unique=True, db_index=True, null=True, blank=True)
    email = models.EmailField(max_length=254, null=True, blank=True)
    nickname = models.CharField(max_length=50, null=True, blank=True)
    student_id = models.CharField(max_length=20, null=True, blank=True)
    department = models.CharField(max_length=100, null=True, blank=True)
    school = models.CharField(max_length=100, null=True, blank=True)
    school_code = models.CharField(max_length=20, null=True, blank=True)
    college_code = models.CharField(max_length=20, null=True, blank=True)
    department_code = models.CharField(max_length=20, null=True, blank=True)
    type_code = models.CharField(max_length=4, null=True, blank=True)
    favorite_restaurants = models.TextField(null=True, blank=True)
    fcm_token = models.CharField(max_length=255, null=True, blank=True)
    preferences = models.JSONField(null=True, blank=True)
    survey_responses = models.JSONField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        if self.kakao_id is not None:
            return f"User {self.kakao_id}"
        if self.apple_id:
            return f"User(apple:{self.apple_id})"
        return f"User {self.username}"


class SocialAccount(models.Model):
    """소셜 로그인 계정 매핑 (Apple 등)"""
    PROVIDER_APPLE = "apple"
    PROVIDER_CHOICES = [(PROVIDER_APPLE, "Apple")]

    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    provider_user_id = models.CharField(max_length=255, db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="social_accounts",
    )
    email = models.EmailField(null=True, blank=True)

    class Meta:
        unique_together = [("provider", "provider_user_id")]

    def __str__(self):
        return f"{self.provider}:{self.provider_user_id}"