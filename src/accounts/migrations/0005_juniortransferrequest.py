from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_juniorprofile'),
    ]

    operations = [
        migrations.CreateModel(
            name='JuniorTransferRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('recipient_iban', models.CharField(max_length=34)),
                ('recipient_name', models.CharField(max_length=200)),
                ('title', models.CharField(max_length=200)),
                ('status', models.CharField(
                    choices=[('PENDING', 'Oczekuje'), ('APPROVED', 'Zatwierdzone'), ('REJECTED', 'Odrzucone')],
                    default='PENDING',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('junior_account', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='transfer_requests',
                    to='accounts.account',
                )),
                ('parent_account', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='junior_transfer_requests_to_review',
                    to='accounts.account',
                )),
            ],
            options={
                'db_table': 'junior_transfer_requests',
                'ordering': ['-created_at'],
            },
        ),
    ]
