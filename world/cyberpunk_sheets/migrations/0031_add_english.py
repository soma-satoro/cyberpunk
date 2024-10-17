from django.db import migrations

def add_english_to_characters(apps, schema_editor):
    CharacterSheet = apps.get_model('cyberpunk_sheets', 'CharacterSheet')
    Language = apps.get_model('languages', 'Language')
    CharacterLanguage = apps.get_model('languages', 'CharacterLanguage')

    english, _ = Language.objects.get_or_create(name="English")
    for character in CharacterSheet.objects.all():
        CharacterLanguage.objects.get_or_create(
            character=character,
            language=english,
            defaults={'level': 4}
        )

class Migration(migrations.Migration):

    dependencies = [
        ('cyberpunk_sheets', '0030_charactersheet_has_cyberarm_and_more'),
    ]

    operations = [
        migrations.RunPython(add_english_to_characters),
    ]