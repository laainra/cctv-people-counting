# Generated by Django 5.0.3 on 2025-01-15 04:06

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0005_remove_company_user_camera_settings_company_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="customusers",
            name="company",
        ),
        migrations.AddField(
            model_name="company",
            name="user",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
