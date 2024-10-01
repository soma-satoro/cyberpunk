from django.db import migrations

def update_character_sheets(apps, schema_editor):
    CharacterSheet = apps.get_model('cyberpunk_sheets', 'CharacterSheet')
    for sheet in CharacterSheet.objects.all():
        sheet.save()  # This will trigger the save method and update the instance

class Migration(migrations.Migration):

    dependencies = [
        ("cyberpunk_sheets", "0011_modify_take_damage"),
    ]

    operations = [
        migrations.RunPython(update_character_sheets),
    ]