# Generated by Django 5.0.3 on 2025-01-14 02:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0003_rename_coorporates_company_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customusers",
            name="email",
            field=models.EmailField(max_length=254, null=True, unique=True),
        ),
    ]