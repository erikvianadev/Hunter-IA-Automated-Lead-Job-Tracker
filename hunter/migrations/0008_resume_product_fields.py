from pathlib import Path

from django.db import migrations, models


def populate_resume_product_fields(apps, schema_editor):
    Resume = apps.get_model('hunter', 'Resume')
    owner_ids = (
        Resume.objects.order_by()
        .values_list('owner_id', flat=True)
        .distinct()
    )

    for resume in Resume.objects.filter(label=""):
        resume.label = Path(resume.original_filename).stem
        resume.save(update_fields=["label"])

    for owner_id in owner_ids:
        owner_resumes = Resume.objects.filter(owner_id=owner_id).order_by('-is_active', '-created_at', '-id')
        active_resume = owner_resumes.filter(is_active=True).first()
        if active_resume is None:
            active_resume = owner_resumes.first()
            if active_resume is None:
                continue
            active_resume.is_active = True
            active_resume.save(update_fields=["is_active"])

        owner_resumes.exclude(id=active_resume.id).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ('hunter', '0007_savedjob_and_application_statuses'),
    ]

    operations = [
        migrations.AddField(
            model_name='resume',
            name='label',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='label'),
        ),
        migrations.AddField(
            model_name='resume',
            name='target_role',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='target role'),
        ),
        migrations.AlterField(
            model_name='resume',
            name='is_active',
            field=models.BooleanField(default=False, verbose_name='is active'),
        ),
        migrations.RunPython(
            populate_resume_product_fields,
            migrations.RunPython.noop,
        ),
    ]
