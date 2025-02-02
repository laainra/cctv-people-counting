# Generated by Django 5.0.3 on 2025-01-18 14:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0007_alter_camera_settings_face_capture_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="personnels",
            name="epmloyee_id",
            field=models.CharField(max_length=100, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="camera_settings",
            name="cam_start",
            field=models.CharField(
                blank=True, default="00:01:00", max_length=200, null=True
            ),
        ),
        migrations.AlterField(
            model_name="camera_settings",
            name="cam_stop",
            field=models.CharField(
                blank=True, default="23:59:00", max_length=200, null=True
            ),
        ),
    ]
