from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_pageview'),
    ]

    operations = [
        migrations.AddField(
            model_name='restaurant',
            name='phone',
            field=models.CharField(blank=True, default='', max_length=60, verbose_name='Телефон'),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='whatsapp',
            field=models.CharField(blank=True, default='', help_text='Только цифры со знаком +, напр. +996700123456', max_length=60, verbose_name='WhatsApp (номер)'),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='instagram',
            field=models.URLField(blank=True, default='', verbose_name='Instagram'),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='telegram',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='Telegram (@username или ссылка)'),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='map_url',
            field=models.URLField(blank=True, default='', verbose_name='Ссылка на карту (2GIS / Google Maps)'),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='tiktok',
            field=models.URLField(blank=True, default='', verbose_name='TikTok'),
        ),
    ]
