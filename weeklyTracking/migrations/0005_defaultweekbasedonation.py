# Generated by Django 4.2.1 on 2023-06-01 14:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('weeklyTracking', '0004_remove_settingregisteredmileage_donation_per_km_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DefaultWeekBaseDonation',
            fields=[
                ('distance', models.IntegerField(primary_key=True, serialize=False)),
                ('base_donation', models.IntegerField()),
                ('last_updated', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
