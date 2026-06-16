# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('transfers', '0003_remove_transfer_scheduled_at_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transfer',
            name='sender_account',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='sent_transfers',
                to='accounts.account',
            ),
        ),
        migrations.AddField(
            model_name='transfer',
            name='sender_iban',
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name='transfer',
            name='sender_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
