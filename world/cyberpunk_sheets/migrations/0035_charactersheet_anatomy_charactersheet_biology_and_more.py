# Generated by Django 4.2.15 on 2024-09-24 04:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cyberpunk_sheets", "0034_alter_charactersheet_character"),
    ]

    operations = [
        migrations.AddField(
            model_name="charactersheet",
            name="anatomy",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="charactersheet",
            name="biology",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="charactersheet",
            name="chemistry",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="charactersheet",
            name="data_science",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="charactersheet",
            name="economics",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="charactersheet",
            name="genetics",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="charactersheet",
            name="nanotechnology",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="charactersheet",
            name="neuroscience",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="charactersheet",
            name="physics",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="charactersheet",
            name="political_science",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="charactersheet",
            name="robotics",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="charactersheet",
            name="sociology",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="charactersheet",
            name="stock_market",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="charactersheet",
            name="zoology",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
