from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '0002_alter_job_preset'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobfile',
            name='crop_mode',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='crop_x',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='crop_y',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='crop_w',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='crop_h',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
