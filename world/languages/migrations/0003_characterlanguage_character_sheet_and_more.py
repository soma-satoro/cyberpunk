# Generated by Django 4.2.15 on 2024-09-22 22:20

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        (
            "cyberpunk_sheets",
            "0033_charactersheet_account_charactersheet_character_and_more",
        ),
        ("languages", "0002_alter_characterlanguage_unique_together_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="characterlanguage",
            name="character_sheet",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="character_languages",
                to="cyberpunk_sheets.charactersheet",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="characterlanguage",
            unique_together={("character_sheet", "language")},
        ),
    ]
