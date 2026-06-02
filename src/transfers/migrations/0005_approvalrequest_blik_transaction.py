import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blik', '0001_initial'),
        ('transfers', '0004_alter_transfer_status_approvalrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='approvalrequest',
            name='blik_transaction',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='approval_request',
                to='blik.bliktransaction',
            ),
        ),
        migrations.AlterField(
            model_name='approvalrequest',
            name='request_type',
            field=models.CharField(
                choices=[
                    ('TRANSFER', 'Przelew'),
                    ('CARD_PAYMENT', 'Płatność kartą'),
                    ('BLIK_PAYMENT', 'Płatność BLIK'),
                ],
                max_length=20,
            ),
        ),
    ]
