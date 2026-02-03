from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '0007_jobfile_crop_enabled'),
    ]

    operations = [
        migrations.CreateModel(
            name='AppSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('concurrency', models.PositiveIntegerField(default=3)),
            ],
        ),
    ]
