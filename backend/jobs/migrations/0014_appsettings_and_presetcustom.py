from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '0013_job_error_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='appsettings',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='appsettings',
            name='default_keep_transparency',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='appsettings',
            name='default_remove_metadata',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='appsettings',
            name='show_debug_details',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='appsettings',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.CreateModel(
            name='PresetCustom',
            fields=[
                ('preset_id', models.CharField(max_length=64, primary_key=True, serialize=False)),
                ('label', models.CharField(max_length=255)),
                ('category', models.CharField(max_length=32)),
                ('width', models.PositiveIntegerField()),
                ('height', models.PositiveIntegerField()),
                ('aspect', models.CharField(max_length=16)),
                ('type_hint', models.CharField(default='photo', max_length=16)),
                ('density', models.CharField(default='standard', max_length=32)),
                ('recommended_format', models.CharField(blank=True, max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
