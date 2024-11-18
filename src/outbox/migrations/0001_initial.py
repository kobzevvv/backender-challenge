# Generated by Django 5.1.2 on 2024-11-17 22:00

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Outbox',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('event_type', models.CharField(max_length=255)),
                ('event_date_time', models.DateTimeField(auto_now_add=True)),
                ('environment', models.CharField(max_length=20)),
                ('event_context', models.JSONField()),
                ('processed_at', models.DateTimeField(null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
