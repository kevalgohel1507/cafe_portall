from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0005_productattribute_attribute'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='categories/'),
        ),
    ]
