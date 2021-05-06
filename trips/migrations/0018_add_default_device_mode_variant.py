# Generated by Django 3.1.8 on 2021-05-06 08:09

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0017_add_transport_mode_variant_unique_constraint'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceDefaultModeVariant',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='default_mode_variants', to='trips.device')),
                ('mode', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='device_default_variants', to='trips.transportmode')),
                ('variant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='device_defaults', to='trips.transportmodevariant')),
            ],
            options={
                'unique_together': {('device', 'mode')},
            },
        ),
    ]