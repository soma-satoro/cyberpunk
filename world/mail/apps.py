from django.apps import AppConfig

class MailConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'world.mail'

    def ready(self):
        import world.mail.signals