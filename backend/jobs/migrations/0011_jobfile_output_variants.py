from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '0010_jobfile_output_dimensions'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobfile',
            name='output_formats',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='output_variants',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='generate_2x',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='generate_sharpened',
            field=models.BooleanField(default=False),
        ),
    ]
