from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '0014_appsettings_and_presetcustom'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appsettings',
            name='concurrency',
            field=models.PositiveIntegerField(default=4),
        ),
    ]
