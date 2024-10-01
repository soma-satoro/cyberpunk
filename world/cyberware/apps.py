from django.apps import AppConfig

class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'world.cyberware'

    def ready(self):
        import world.cyberware.signals

class CyberpunkSheetsConfig(AppConfig):
    name = 'world.cyberpunk_sheets'
    default_auto_field = 'django.db.models.BigAutoField'
    def ready(self):
        import world.cyberpunk_sheets.models

class LanguagesConfig(AppConfig):
    name = 'world.languages'
    default_auto_field = 'django.db.models.BigAutoField'
    def ready(self):
        import world.languages.models