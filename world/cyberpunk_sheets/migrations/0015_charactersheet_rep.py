# Generated by Django 4.2.15 on 2024-09-16 01:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cyberpunk_sheets", "0014_charactersheet_eurodollars"),
    ]

    operations = [
        migrations.AddField(
            model_name="charactersheet",
            name="rep",
            field=models.IntegerField(default=0),
        ),
    ]
