# Generated by Django 4.2.15 on 2024-09-20 20:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0010_ammunition_weapon_ammo_type_weapon_current_ammo_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="weapon",
            name="clip",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
