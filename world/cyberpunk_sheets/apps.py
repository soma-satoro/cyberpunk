from django.apps import AppConfig

class CyberpunkSheetsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'world.cyberpunk_sheets'

    def ready(self):
        import world.cyberpunk_sheets.signals