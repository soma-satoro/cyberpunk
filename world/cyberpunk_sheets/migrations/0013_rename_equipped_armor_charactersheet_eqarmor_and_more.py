# Generated by Django 4.2.15 on 2024-09-14 05:50

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("cyberpunk_sheets", "0012_update_character_sheets"),
    ]

    operations = [
        migrations.RenameField(
            model_name="charactersheet",
            old_name="equipped_armor",
            new_name="eqarmor",
        ),
        migrations.RenameField(
            model_name="charactersheet",
            old_name="equipped_weapon",
            new_name="eqweapon",
        ),
    ]
