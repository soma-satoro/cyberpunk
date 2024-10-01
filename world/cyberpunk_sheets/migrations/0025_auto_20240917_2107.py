from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('cyberpunk_sheets', '0024_migrate_language_data'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='charactersheet',
            name='languages',
        ),
        migrations.RenameField(
            model_name='charactersheet',
            old_name='new_languages',
            new_name='languages',
        ),
        migrations.DeleteModel(
            name='Language',
        ),
    ]