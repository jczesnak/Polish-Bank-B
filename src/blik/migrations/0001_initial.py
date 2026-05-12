import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BlikCode',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=6)),
                ('status', models.CharField(
                    choices=[('ACTIVE', 'Aktywny'), ('USED', 'Użyty'), ('EXPIRED', 'Wygasły')],
                    default='ACTIVE',
                    max_length=10,
                )),
                ('expires_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='blik_codes',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('account', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='blik_codes',
                    to='accounts.account',
                )),
            ],
            options={'db_table': 'blik_codes', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='BlikTransaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('klik_transaction_id', models.UUIDField(unique=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('currency', models.CharField(default='PLN', max_length=3)),
                ('merchant_name', models.CharField(blank=True, max_length=200)),
                ('status', models.CharField(
                    choices=[
                        ('PENDING', 'Oczekująca'),
                        ('AUTHORIZED', 'Autoryzowana'),
                        ('COMPLETED', 'Zakończona'),
                        ('REJECTED', 'Odrzucona'),
                        ('TIMEOUT', 'Timeout'),
                    ],
                    default='PENDING',
                    max_length=15,
                )),
                ('reject_reason', models.CharField(
                    blank=True,
                    choices=[
                        ('INSUFFICIENT_FUNDS', 'Brak środków'),
                        ('USER_DECLINED', 'Odrzucono przez użytkownika'),
                        ('AML_BLOCK', 'Blokada AML'),
                        ('OTHER', 'Inny powód'),
                    ],
                    max_length=30,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='blik_transactions',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('account', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='blik_transactions',
                    to='accounts.account',
                )),
            ],
            options={'db_table': 'blik_transactions', 'ordering': ['-created_at']},
        ),
    ]
