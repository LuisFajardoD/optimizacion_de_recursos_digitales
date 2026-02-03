from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '0003_jobfile_crop_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobfile',
            name='original_width',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='original_height',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='orientation',
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='aspect_label',
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='has_transparency',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='analysis_type',
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='metadata_tags',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='keep_metadata',
            field=models.BooleanField(default=False),
        ),
    ]
