# world/netrunning/apps.py

from django.apps import AppConfig

class NetrunningConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'world.netrunning'

    def ready(self):
        import world.netrunning.signals