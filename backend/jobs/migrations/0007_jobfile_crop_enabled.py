from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '0006_jobfile_override_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobfile',
            name='crop_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='crop_aspect',
            field=models.CharField(blank=True, max_length=16),
        ),
    ]
