from django.apps import AppConfig

class CyberpunkSheetsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'world.factions'

    def ready(self):
        import world.factions.signals