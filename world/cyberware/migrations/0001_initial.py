# Generated by Django 4.2.15 on 2024-09-13 16:59

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Cyberware",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("type", models.CharField(max_length=50)),
                ("slots", models.IntegerField(default=1)),
                ("humanity_loss", models.IntegerField(default=0)),
                ("cost", models.IntegerField(default=0)),
                ("description", models.TextField(blank=True)),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
