# File: 0001_initial.py

from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Language",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("description", models.TextField(blank=True)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="CharacterLanguage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("level", models.IntegerField(default=1)),
                ("character", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="character_languages", to="cyberpunk_sheets.charactersheet")),
                ("language", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="languages.language")),
            ],
            options={
                "unique_together": {("character", "language")},
            },
        ),
    ]