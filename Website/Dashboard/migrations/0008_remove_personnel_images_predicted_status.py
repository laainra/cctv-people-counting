# Generated by Django 5.0.3 on 2024-10-04 06:44

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Dashboard', '0007_alter_personnel_entries_presence_status_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='personnel_images',
            name='predicted_status',
        ),
    ]