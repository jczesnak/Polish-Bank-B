import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('blik', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PhoneAlias',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('phone', models.CharField(max_length=16, unique=True)),
                ('klik_alias_id', models.UUIDField(blank=True, null=True)),
                ('zone', models.CharField(default='PL', max_length=2)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('account', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='phone_aliases',
                    to='accounts.account',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='phone_aliases',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'blik_phone_aliases', 'ordering': ['-created_at']},
        ),
    ]
