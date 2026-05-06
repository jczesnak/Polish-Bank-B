from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transfers', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='transfer',
            name='scheduled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
