# Generated by Django 5.0.3 on 2024-05-16 03:43

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Camera_Settings",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("cam_name", models.CharField(max_length=200)),
                ("feed_src", models.CharField(max_length=200)),
                ("x1", models.IntegerField(default=0)),
                ("y1", models.IntegerField(default=0)),
                ("x2", models.IntegerField(default=0)),
                ("y2", models.IntegerField(default=0)),
                ("x3", models.IntegerField(default=0)),
                ("y3", models.IntegerField(default=0)),
                ("x4", models.IntegerField(default=0)),
                ("y4", models.IntegerField(default=0)),
                ("x5", models.IntegerField(default=0)),
                ("y5", models.IntegerField(default=0)),
                ("x6", models.IntegerField(default=0)),
                ("y6", models.IntegerField(default=0)),
                ("x7", models.IntegerField(default=0)),
                ("y7", models.IntegerField(default=0)),
                ("x8", models.IntegerField(default=0)),
                ("y8", models.IntegerField(default=0)),
                ("cam_is_active", models.BooleanField(default=False)),
                ("gender_detection", models.BooleanField(default=False)),
                ("face_detection", models.BooleanField(default=False)),
                ("cam_start", models.CharField(max_length=200)),
                ("cam_stop", models.CharField(max_length=200)),
                ("createdAt", models.DateTimeField(auto_now_add=True)),
                ("updatedAt", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Personnels",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                (
                    "gender",
                    models.CharField(
                        choices=[("M", "Male"), ("F", "Female")], max_length=100
                    ),
                ),
                ("createdAt", models.DateTimeField(auto_now_add=True, null=True)),
                ("updatedAt", models.DateTimeField(auto_now=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="Counted_Instances",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("timestamp", models.CharField(max_length=200)),
                ("male_entries", models.IntegerField(default=0)),
                ("female_entries", models.IntegerField(default=0)),
                ("unknown_gender_entries", models.IntegerField(default=0)),
                ("people_exits", models.IntegerField(default=0)),
                ("people_inside", models.IntegerField(default=0)),
                (
                    "camera",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="Dashboard.camera_settings",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Personnel_Entries",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=200)),
                ("timestamp", models.CharField(max_length=200)),
                (
                    "camera",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="Dashboard.camera_settings",
                    ),
                ),
            ],
        ),
    ]
