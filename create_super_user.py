import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from django.contrib.auth.models import User

username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "admin123")
email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@email.com")

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print(f"Usuário {username} criado com sucesso!")
else:
    print(f"Usuário {username} já existe.")