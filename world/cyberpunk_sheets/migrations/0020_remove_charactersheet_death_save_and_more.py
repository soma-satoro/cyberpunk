# Generated by Django 4.2.15 on 2024-09-17 05:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("cyberpunk_sheets", "0019_language_charactersheet_languages"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="charactersheet",
            name="death_save",
        ),
        migrations.RemoveField(
            model_name="charactersheet",
            name="humanity",
        ),
        migrations.RemoveField(
            model_name="charactersheet",
            name="serious_wounds",
        ),
    ]
