# Generated by Django 4.2.15 on 2024-09-19 06:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "netrunning",
            "0003_remove_program_cyberdeck_remove_program_description_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="program",
            name="atk",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="program",
            name="cost",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="program",
            name="dfv",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="program",
            name="effect",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="program",
            name="icon",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="program",
            name="name",
            field=models.CharField(default="Unnamed Program", max_length=255),
        ),
        migrations.AddField(
            model_name="program",
            name="rez",
            field=models.IntegerField(default=0),
        ),
    ]
