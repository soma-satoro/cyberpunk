# Generated manually for Mission Board

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("objects", "0014_defaultobject_defaultcharacter_defaultexit_and_more"),
        ("factions", "0001_initial"),
        ("jobs", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Mission",
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
                ("description", models.TextField()),
                ("posted_date", models.DateTimeField(default=timezone.now)),
                ("due_date", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("active", "Active"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="open",
                        max_length=20,
                    ),
                ),
                ("posted_by_staff", models.BooleanField(default=False)),
                ("money_amount", models.IntegerField(default=0)),
                ("money_pay_on_delivery", models.BooleanField(default=False)),
                ("rep_amount", models.IntegerField(default=0)),
                ("voucher_rewards", models.JSONField(default=list)),
                ("item_rewards", models.JSONField(default=list)),
                ("rewards_pay_on_delivery", models.BooleanField(default=False)),
                ("failure_penalty_amount", models.IntegerField(default=0)),
                (
                    "failure_penalty_scope",
                    models.CharField(
                        blank=True,
                        choices=[("leader", "Leader only"), ("team", "Entire team")],
                        default="leader",
                        max_length=10,
                    ),
                ),
                (
                    "gm_type",
                    models.CharField(
                        choices=[
                            ("assigned", "Assigned"),
                            ("pickup", "Pickup"),
                        ],
                        default="pickup",
                        max_length=20,
                    ),
                ),
                ("updates", models.JSONField(default=list)),
                ("scene_description", models.TextField(blank=True)),
                ("scene_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "posted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="posted_missions",
                        to="objects.objectdb",
                    ),
                ),
                (
                    "gm",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="gm_missions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "job",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="mission",
                        to="jobs.job",
                    ),
                ),
                (
                    "faction",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="missions",
                        to="factions.faction",
                    ),
                ),
            ],
            options={
                "ordering": ["-posted_date"],
            },
        ),
        migrations.CreateModel(
            name="MissionTeamMember",
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
                ("order", models.IntegerField(default=0)),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="objects.objectdb",
                    ),
                ),
                (
                    "mission",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="team_members",
                        to="mission_board.mission",
                    ),
                ),
            ],
            options={
                "ordering": ["order"],
                "unique_together": {("mission", "character")},
            },
        ),
    ]
