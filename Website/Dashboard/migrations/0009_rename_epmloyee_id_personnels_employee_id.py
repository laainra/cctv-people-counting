# Generated by Django 5.0.3 on 2025-01-18 14:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0008_personnels_epmloyee_id_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="personnels",
            old_name="epmloyee_id",
            new_name="employee_id",
        ),
    ]
