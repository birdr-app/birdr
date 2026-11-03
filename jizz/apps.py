from django.apps import AppConfig

class JizzConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'jizz'

    def ready(self):
        import jizz.signals  # noqa
        from django.conf import settings
        from django.core.mail.utils import DNS_NAME

        # make_msgid() reads this cached name; set it so it skips socket.getfqdn().
        DNS_NAME._fqdn = settings.EMAIL_MESSAGE_ID_DOMAIN 