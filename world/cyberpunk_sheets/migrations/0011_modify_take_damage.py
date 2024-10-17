from django.db import migrations

def add_take_damage_method(apps, schema_editor):
    CharacterSheet = apps.get_model('cyberpunk_sheets', 'CharacterSheet')
    for sheet in CharacterSheet.objects.all():
        sheet.save()

class Migration(migrations.Migration):

    dependencies = [
        ("cyberpunk_sheets", "0010_charactersheet_equipped_armor_and_more"),
    ]


    operations = [
        migrations.RunPython(add_take_damage_method),
    ]