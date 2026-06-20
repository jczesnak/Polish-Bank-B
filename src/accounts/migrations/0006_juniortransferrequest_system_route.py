from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_juniortransferrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='juniortransferrequest',
            name='system_route',
            field=models.CharField(
                choices=[
                    ('INTERNAL', 'Wewnętrzny'),
                    ('ELIXIR', 'Elixir'),
                    ('EXPRESS_ELIXIR', 'Express Elixir'),
                    ('SORBNET', 'Sorbnet'),
                ],
                default='ELIXIR',
                max_length=20,
            ),
        ),
    ]
