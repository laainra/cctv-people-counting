# Generated by Django 5.0.3 on 2025-01-15 12:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0006_remove_customusers_company_company_user"),
    ]

    operations = [
        migrations.AlterField(
            model_name="camera_settings",
            name="face_capture",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="camera_settings",
            name="face_detection",
            field=models.BooleanField(default=True),
        ),
    ]