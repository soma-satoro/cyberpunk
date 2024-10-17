from django.db import migrations, models
import django.db.models.deletion

def populate_account_field(apps, schema_editor):
    CharacterSheet = apps.get_model('cyberpunk_sheets', 'CharacterSheet')
    for sheet in CharacterSheet.objects.all():
        if not sheet.account:
            if hasattr(sheet, 'db_object') and sheet.db_object and sheet.db_object.account:
                sheet.account = sheet.db_object.account
                sheet.save()
            else:
                print(f"Warning: CharacterSheet {sheet.id} has no associated account. It will be deleted.")
                sheet.delete()

class Migration(migrations.Migration):

    dependencies = [
        ('cyberpunk_sheets', '0003_remove_charactersheet_db_object_and_more'),  # replace with your actual previous migration
    ]


    operations = [
        migrations.RunPython(populate_account_field),
        migrations.AlterField(
            model_name='charactersheet',
            name='account',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='character_sheet', to='accounts.accountdb'),
        ),
    ]
