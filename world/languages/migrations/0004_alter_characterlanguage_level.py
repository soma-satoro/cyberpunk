# Generated by Django 4.2.15 on 2024-09-23 20:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("languages", "0003_characterlanguage_character_sheet_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="characterlanguage",
            name="level",
            field=models.IntegerField(default=1),
        ),
    ]
