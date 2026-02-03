from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '0004_jobfile_analysis_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobfile',
            name='recommended_preset_id',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='recommended_preset_label',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='recommended_formats',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='recommended_quality',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='recommended_crop_mode',
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='recommended_crop_reason',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='recommended_notes',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
