from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '0009_alter_appsettings_id_alter_job_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobfile',
            name='output_height',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='output_width',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
