# Generated by Django 4.2.15 on 2024-09-20 05:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cyberware", "0002_cyberware_requirements"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cyberware",
            name="requirements",
            field=models.TextField(blank=True, default=""),
        ),
    ]
