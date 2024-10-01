from django.db import migrations

def update_inventory_relationships(apps, schema_editor):
    Inventory = apps.get_model('inventory', 'Inventory')
    CharacterSheet = apps.get_model('cyberpunk_sheets', 'CharacterSheet')
    
    for inventory in Inventory.objects.all():
        if inventory.character and hasattr(inventory.character, 'character_sheet'):
            character_sheet = inventory.character.character_sheet
            inventory.character = character_sheet
            inventory.save()

class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0002_alter_armor_description_alter_armor_locations_and_more'),  # replace with actual previous migration
    ]

    operations = [
        migrations.RunPython(update_inventory_relationships),
    ]