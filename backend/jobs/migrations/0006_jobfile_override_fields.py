from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '0005_jobfile_recommendation_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobfile',
            name='selected_preset_id',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='output_format',
            field=models.CharField(blank=True, max_length=16, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='quality_webp',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='quality_jpg',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='quality_avif',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='keep_transparency',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='rename_pattern',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='normalize_lowercase',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='normalize_remove_accents',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='normalize_replace_spaces',
            field=models.CharField(default='-', max_length=16),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='normalize_collapse_dashes',
            field=models.BooleanField(default=True),
        ),
    ]
