# Generated migration for Elflines Online

from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('cyberpunk_sheets', '__first__'),
        ('objects', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Elfline',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('display_name', models.CharField(blank=True, max_length=120)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('leader', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='led_elflines', to='objects.objectdb')),
            ],
            options={
                'verbose_name': 'Elfline',
                'verbose_name_plural': 'Elflines',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='ElflineSheet',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('elfname', models.CharField(blank=True, max_length=80)),
                ('gp', models.IntegerField(default=200, validators=[django.core.validators.MinValueValidator(0)])),
                ('revive_sickness', models.BooleanField(default=False)),
                ('rank', models.PositiveIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(10)])),
                ('title', models.CharField(blank=True, max_length=50)),
                ('stat_increases_by_rank', models.JSONField(default=list)),
                ('intelligence', models.PositiveIntegerField(default=3, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)])),
                ('reflexes', models.PositiveIntegerField(default=3, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)])),
                ('dexterity', models.PositiveIntegerField(default=3, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)])),
                ('technology', models.PositiveIntegerField(default=3, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)])),
                ('cool', models.PositiveIntegerField(default=3, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)])),
                ('willpower', models.PositiveIntegerField(default=3, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)])),
                ('move', models.PositiveIntegerField(default=3, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)])),
                ('body', models.PositiveIntegerField(default=3, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)])),
                ('empathy', models.PositiveIntegerField(default=3, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)])),
                ('skills', models.JSONField(default=dict)),
                ('max_hp', models.PositiveIntegerField(default=0)),
                ('current_hp', models.PositiveIntegerField(default=0)),
                ('equipped_armor', models.CharField(blank=True, max_length=80)),
                ('equipped_weapon', models.CharField(blank=True, max_length=80)),
                ('inventory', models.JSONField(default=list)),
                ('is_complete', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('character', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='elfline_sheet', to='objects.objectdb')),
                ('character_sheet', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='elfline_sheet', to='cyberpunk_sheets.charactersheet')),
                ('elfline', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='members', to='elflines.elfline')),
                ('last_camp_room', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='objects.objectdb')),
            ],
            options={
                'verbose_name': 'Elfline Sheet',
                'verbose_name_plural': 'Elfline Sheets',
            },
        ),
        migrations.CreateModel(
            name='ElflineMembership',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(blank=True, max_length=50)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('character', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='elfline_memberships', to='objects.objectdb')),
                ('elfline', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='elflines.elfline')),
            ],
            options={
                'unique_together': {('elfline', 'character')},
                'verbose_name': 'Elfline Membership',
                'verbose_name_plural': 'Elfline Memberships',
            },
        ),
    ]
