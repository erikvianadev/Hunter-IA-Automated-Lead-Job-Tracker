from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hunter', '0005_alter_resume_parse_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SeniorityAssessment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('internship_score', models.PositiveSmallIntegerField(default=0, verbose_name='internship score')),
                ('junior_score', models.PositiveSmallIntegerField(default=0, verbose_name='junior score')),
                ('mid_score', models.PositiveSmallIntegerField(default=0, verbose_name='mid score')),
                ('senior_score', models.PositiveSmallIntegerField(default=0, verbose_name='senior score')),
                ('freelance_score', models.PositiveSmallIntegerField(default=0, verbose_name='freelance score')),
                ('recommended_track', models.CharField(max_length=32, verbose_name='recommended track')),
                ('reasoning', models.JSONField(blank=True, default=dict, verbose_name='reasoning')),
                ('resume', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='seniority_assessment', to='hunter.resume', verbose_name='resume')),
            ],
            options={
                'verbose_name': 'seniority assessment',
                'verbose_name_plural': 'seniority assessments',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='JobMatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('match_score', models.PositiveSmallIntegerField(default=0, verbose_name='match score')),
                ('strengths', models.JSONField(blank=True, default=list, verbose_name='strengths')),
                ('gaps', models.JSONField(blank=True, default=list, verbose_name='gaps')),
                ('recommendation', models.CharField(max_length=255, verbose_name='recommendation')),
                ('reasoning', models.JSONField(blank=True, default=dict, verbose_name='reasoning')),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='resume_matches', to='hunter.job', verbose_name='job')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='job_matches', to=settings.AUTH_USER_MODEL, verbose_name='owner')),
                ('resume', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='job_matches', to='hunter.resume', verbose_name='resume')),
            ],
            options={
                'verbose_name': 'job match',
                'verbose_name_plural': 'job matches',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='jobmatch',
            constraint=models.UniqueConstraint(fields=('owner', 'resume', 'job'), name='uniq_owner_resume_job_match'),
        ),
        migrations.AddIndex(
            model_name='jobmatch',
            index=models.Index(fields=['owner', 'created_at'], name='jobmatch_owner_created_idx'),
        ),
    ]
