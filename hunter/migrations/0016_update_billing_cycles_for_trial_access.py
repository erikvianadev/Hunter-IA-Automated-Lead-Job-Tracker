from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hunter', '0015_resume_likeness_parse_statuses'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billinginvoice',
            name='billing_cycle',
            field=models.CharField(
                choices=[
                    ('free', 'Free'),
                    ('trial_15', '15 days'),
                    ('trial_30', '30 days'),
                    ('trial_90', '90 days'),
                ],
                default='free',
                max_length=16,
                verbose_name='billing cycle',
            ),
        ),
        migrations.AlterField(
            model_name='billingsubscription',
            name='billing_cycle',
            field=models.CharField(
                choices=[
                    ('free', 'Free'),
                    ('trial_15', '15 days'),
                    ('trial_30', '30 days'),
                    ('trial_90', '90 days'),
                ],
                default='free',
                max_length=16,
                verbose_name='billing cycle',
            ),
        ),
    ]
