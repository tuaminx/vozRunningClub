# Generated by Django 4.2.1 on 2023-06-05 09:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('weeklyTracking', '0011_alter_stravarunner_voz_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stravarunner',
            name='strava_refresh_token',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
    ]
