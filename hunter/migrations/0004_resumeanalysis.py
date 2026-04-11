from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hunter', '0003_resume'),
    ]

    operations = [
        migrations.CreateModel(
            name='ResumeAnalysis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('overall_score', models.PositiveSmallIntegerField(default=0, verbose_name='overall score')),
                ('structure_score', models.PositiveSmallIntegerField(default=0, verbose_name='structure score')),
                ('clarity_score', models.PositiveSmallIntegerField(default=0, verbose_name='clarity score')),
                ('market_fit_score', models.PositiveSmallIntegerField(default=0, verbose_name='market fit score')),
                ('project_score', models.PositiveSmallIntegerField(default=0, verbose_name='project score')),
                ('strengths', models.JSONField(blank=True, default=list, verbose_name='strengths')),
                ('weaknesses', models.JSONField(blank=True, default=list, verbose_name='weaknesses')),
                ('recommendations', models.JSONField(blank=True, default=list, verbose_name='recommendations')),
                ('raw_summary', models.JSONField(blank=True, default=dict, verbose_name='raw summary')),
                ('resume', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='analysis', to='hunter.resume', verbose_name='resume')),
            ],
            options={
                'verbose_name': 'resume analysis',
                'verbose_name_plural': 'resume analyses',
                'ordering': ['-created_at'],
            },
        ),
    ]
