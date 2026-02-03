from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '0011_jobfile_output_variants'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobfile',
            name='cropped',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobfile',
            name='metadata_removed',
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
