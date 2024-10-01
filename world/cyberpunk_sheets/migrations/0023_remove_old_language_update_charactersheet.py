# New migration file
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('cyberpunk_sheets', '0022_migrate_language_data'),
        ('languages', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='charactersheet',
            name='new_languages',
            field=models.ManyToManyField(
                related_name='speakers',
                through='languages.CharacterLanguage',
                to='languages.language',
            ),
        ),
    ]