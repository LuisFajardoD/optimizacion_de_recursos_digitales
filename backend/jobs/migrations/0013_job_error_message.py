from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '0012_jobfile_report_flags'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='error_message',
            field=models.TextField(blank=True),
        ),
    ]
