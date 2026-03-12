from django.apps import AppConfig

class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'world.inventory'

    def ready(self):
        import world.inventory.signals

