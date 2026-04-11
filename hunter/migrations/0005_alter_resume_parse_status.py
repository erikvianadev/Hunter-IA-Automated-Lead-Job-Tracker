from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hunter', '0004_resumeanalysis'),
    ]

    operations = [
        migrations.AlterField(
            model_name='resume',
            name='parse_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('processing', 'Processing'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                    ('empty_text', 'Empty Text'),
                    ('unsupported_structure', 'Unsupported Structure'),
                ],
                default='pending',
                max_length=32,
                verbose_name='parse status',
            ),
        ),
    ]
