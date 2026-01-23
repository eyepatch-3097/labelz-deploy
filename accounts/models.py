import uuid
import random
import string
import hashlib
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
import hashlib
import secrets
from datetime import timedelta


class Org(models.Model):
    name = models.CharField(max_length=255)
    # domain is for company emails (dotswitch.space); can be null for generic-email orgs
    domain = models.CharField(max_length=255, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    org_code = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.name or (self.domain or "Org")

    def _generate_org_code(self) -> str:
        # Org prefix: first 3 letters of name (fallback to domain or "ORG")
        source = (self.name or self.domain or "ORG").strip()
        letters = ''.join(ch for ch in source if ch.isalnum())
        prefix = (letters[:3] or "ORG").upper()

        # Random 5-char alphanumeric
        rand_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

        # 6-char hash from uuid
        hash_part = uuid.uuid4().hex[:6].upper()

        return f"{prefix}{rand_part}{hash_part}"

    def save(self, *args, **kwargs):
        if not self.org_code:
            self.org_code = self._generate_org_code()
        super().save(*args, **kwargs)

class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """
        Create and save a user with the given email and password.
        """
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)

def generate_user_code(user):
    """
    Generate a stable-looking user code:
    - org first 3 chars (or ORG)
    - user name/email first 3 chars (or USR)
    - 5 random letters/digits
    - 4-char hash suffix
    Example: TESSID8K2M3A7F
    """

    # Org prefix
    if getattr(user, "org", None) and user.org and user.org.name:
        org_prefix = user.org.name[:3].upper()
    else:
        org_prefix = "ORG"

    # Name/email prefix
    full_name = user.get_full_name() if hasattr(user, "get_full_name") else ""
    if full_name:
        name_source = full_name
    else:
        # fall back to email before @
        name_source = (user.email or "user").split('@')[0]
    name_prefix = (name_source[:3] or "USR").upper()

    # Random part
    rand_part = ''.join(
        random.choices(string.ascii_uppercase + string.digits, k=5)
    )

    base = f"{org_prefix}{name_prefix}{rand_part}"

    # Short hash for extra uniqueness
    hash_suffix = hashlib.sha1(base.encode("utf-8")).hexdigest()[:4].upper()

    return base + hash_suffix

class User(AbstractUser):
    # Remove username; use email as the unique identifier
    username = None
    email = models.EmailField(unique=True)
    email_is_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    org = models.ForeignKey(
        Org,
        related_name='users',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    ROLE_ADMIN = 'ADMIN'
    ROLE_OPERATOR = 'OPERATOR'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_OPERATOR, 'Operator'),
    ]
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_OPERATOR,
    )

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_PENDING = 'PENDING'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PENDING, 'Pending Approval'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )

    # NEW: external ID for admins/operators
    user_code = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # email & password only

    objects = UserManager()

    def __str__(self):
        return self.email

    def _org_prefix(self) -> str:
        """
        org first 3 chars from org.name or org.domain
        """
        if self.org:
            source = (self.org.name or self.org.domain or "ORG").strip()
        else:
            source = "ORG"

        letters = ''.join(ch for ch in source if ch.isalnum())
        return (letters[:3] or "ORG").upper()

    def _name_prefix(self) -> str:
        """
        name first 3 chars from full name or email local-part.
        This is the 'admin name first 3 chars' / operator name.
        """
        fullname = (self.get_full_name() or "").strip()
        if fullname:
            letters = ''.join(ch for ch in fullname if ch.isalpha())
        else:
            local_part = self.email.split("@")[0]
            letters = ''.join(ch for ch in local_part if ch.isalnum())

        return (letters[:3] or "USR").upper()

    def _generate_user_code(self) -> str:
        org_prefix = self._org_prefix()
        name_prefix = self._name_prefix()

        # Random 5-char alphanumeric
        rand_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

        # 6-char hash from uuid
        hash_part = uuid.uuid4().hex[:6].upper()

        # Pattern: ORG(3) + NAME(3) + RANDOM(5) + HASH(6)
        return f"{org_prefix}{name_prefix}{rand_part}{hash_part}"

    def save(self, *args, **kwargs):
        # If existing user and role changed, force regeneration of user_code
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
            if old and old.role != self.role:
                self.user_code = None

        # Generate user_code if missing (admin vs user handled inside helper)
        if not self.user_code:
            self.user_code = self._generate_user_code()  # use your existing helper

        super().save(*args, **kwargs)


class OrgJoinRequest(models.Model):
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name='join_requests')
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='join_request',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"JoinRequest({self.user.email} -> {self.org})"


class EmailOTP(models.Model):
    PURPOSE_VERIFY = "VERIFY_EMAIL"
    PURPOSE_RESET = "RESET_PASSWORD"
    PURPOSE_CHOICES = [
        (PURPOSE_VERIFY, "Verify Email"),
        (PURPOSE_RESET, "Reset Password"),
    ]

    email = models.EmailField(db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="email_otps"
    )
    purpose = models.CharField(max_length=32, choices=PURPOSE_CHOICES)
    otp_hash = models.CharField(max_length=128)
    attempts = models.PositiveIntegerField(default=0)

    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["email", "purpose", "-created_at"]),
        ]

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def is_consumed(self):
        return self.consumed_at is not None

    @staticmethod
    def make_otp() -> str:
        # 6-digit numeric OTP
        return f"{secrets.randbelow(1_000_000):06d}"

    @staticmethod
    def hash_otp(raw_otp: str) -> str:
        # hash with SECRET_KEY so DB leak doesn’t expose OTPs
        base = f"{settings.SECRET_KEY}:{raw_otp}".encode("utf-8")
        return hashlib.sha256(base).hexdigest()

    @classmethod
    def create_otp(cls, *, email: str, purpose: str, user=None, ttl_minutes: int = 10):
        raw = cls.make_otp()
        row = cls.objects.create(
            email=email,
            user=user,
            purpose=purpose,
            otp_hash=cls.hash_otp(raw),
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
        )
        return row, raw

    def verify(self, raw_otp: str, max_attempts: int = 5) -> bool:
        if self.is_consumed() or self.is_expired():
            return False
        if self.attempts >= max_attempts:
            return False

        self.attempts += 1
        ok = (self.otp_hash == self.hash_otp(raw_otp))
        if ok:
            self.consumed_at = timezone.now()
        self.save(update_fields=["attempts", "consumed_at"])
        return ok