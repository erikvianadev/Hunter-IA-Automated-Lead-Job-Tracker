from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hunter", "0012_alter_resume_parse_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="job",
            name="url",
            field=models.URLField(blank=True, max_length=1000, verbose_name="url"),
        ),
    ]
