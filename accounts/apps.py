from django.apps import AppConfig
import posthog

class AccountsConfig(AppConfig):
    name = 'accounts'


class AccountsAppConfig(AppConfig):  
    name = "accounts_labelz"  
    def ready(self):  
        posthog.api_key = 'phc_6lykc5rzsPib7kA0aO7nNM9L3Y1nTU1jQ61GYA6WTK3' 
        posthog.host = 'https://us.i.posthog.com'  
