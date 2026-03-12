# Migration: faction missions, GM character, faction visibility

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mission_board", "0001_initial"),
        ("factions", "0001_initial"),
        ("objects", "0014_defaultobject_defaultcharacter_defaultexit_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="mission",
            name="faction_rep_amount",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="mission",
            name="faction_visibility",
            field=models.CharField(
                choices=[("public", "Public"), ("faction_only", "Faction Only")],
                default="public",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="mission",
            name="gm_character",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="gm_missions",
                to="objects.objectdb",
            ),
        ),
        migrations.CreateModel(
            name="FactionMissionPoster",
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
                (
                    "character",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="objects.objectdb",
                    ),
                ),
                (
                    "faction",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mission_posters",
                        to="factions.faction",
                    ),
                ),
            ],
            options={
                "unique_together": {("faction", "character")},
            },
        ),
    ]
