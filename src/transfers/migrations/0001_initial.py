import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Transfer',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('recipient_iban', models.CharField(max_length=32)),
                ('recipient_name', models.CharField(max_length=255)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('title', models.CharField(max_length=255)),
                ('system_route', models.CharField(
                    choices=[
                        ('INTERNAL', 'Wewnętrzny'),
                        ('ELIXIR', 'Elixir'),
                        ('EXPRESS_ELIXIR', 'Express Elixir'),
                        ('SORBNET', 'Sorbnet'),
                    ],
                    default='ELIXIR',
                    max_length=20,
                )),
                ('status', models.CharField(
                    choices=[
                        ('PENDING', 'Oczekujący'),
                        ('PROCESSING', 'W realizacji'),
                        ('COMPLETED', 'Zrealizowany'),
                        ('FAILED', 'Nieudany'),
                        ('CANCELLED', 'Anulowany'),
                    ],
                    default='PENDING',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('sender_account', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='sent_transfers',
                    to='accounts.account',
                )),
            ],
            options={
                'db_table': 'transfers',
                'ordering': ['-created_at'],
            },
        ),
    ]
