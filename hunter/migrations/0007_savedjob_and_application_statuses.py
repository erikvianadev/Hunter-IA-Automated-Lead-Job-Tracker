from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_job_application_statuses(apps, schema_editor):
    JobApplication = apps.get_model('hunter', 'JobApplication')
    status_map = {
        'NOT_APPLIED': 'saved',
        'APPLIED': 'applied',
        'INTERVIEW': 'interview',
        'REJECTED': 'rejected',
        'OFFER': 'offer',
    }
    for legacy_status, next_status in status_map.items():
        JobApplication.objects.filter(status=legacy_status).update(status=next_status)


class Migration(migrations.Migration):

    dependencies = [
        ('hunter', '0006_seniorityassessment_jobmatch'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SavedJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='saved_by_users', to='hunter.job', verbose_name='job')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='saved_jobs', to=settings.AUTH_USER_MODEL, verbose_name='owner')),
            ],
            options={
                'verbose_name': 'saved job',
                'verbose_name_plural': 'saved jobs',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['owner', 'created_at'], name='savedjob_owner_created_idx')],
                'constraints': [models.UniqueConstraint(fields=('owner', 'job'), name='unique_owner_saved_job')],
            },
        ),
        migrations.AlterField(
            model_name='jobapplication',
            name='status',
            field=models.CharField(choices=[('saved', 'Saved'), ('applied', 'Applied'), ('interview', 'Interview'), ('rejected', 'Rejected'), ('offer', 'Offer'), ('archived', 'Archived')], default='saved', max_length=20, verbose_name='status'),
        ),
        migrations.RunPython(
            migrate_job_application_statuses,
            migrations.RunPython.noop,
        ),
    ]
