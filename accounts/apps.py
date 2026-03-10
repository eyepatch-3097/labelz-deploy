from django.apps import AppConfig
from django.conf import settings
import posthog


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        posthog.api_key = settings.POSTHOG_API_KEY
        posthog.host = getattr(settings, "POSTHOG_HOST", "https://us.i.posthog.com")
