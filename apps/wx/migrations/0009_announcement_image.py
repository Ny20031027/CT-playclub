from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wx', '0008_add_pre_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='announcement',
            name='image',
            field=models.CharField(blank=True, max_length=500, verbose_name='图片URL'),
        ),
    ]
