import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.getenv("DJANGO_SUPERUSER_USERNAME")
email = os.getenv("DJANGO_SUPERUSER_EMAIL")
password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

if not username or not email or not password:
    print("Superuser env vars are missing. Skipping superuser bootstrap.")
    raise SystemExit(0)

user, created = User.objects.get_or_create(
    username=username,
    defaults={
        "email": email,
        "is_staff": True,
        "is_superuser": True,
        "is_active": True,
    },
)

if created:
    user.set_password(password)
    user.save()
    print(f"Superuser '{username}' created successfully.")
else:
    updated = False
    if user.email != email:
        user.email = email
        updated = True
    if not user.is_staff:
        user.is_staff = True
        updated = True
    if not user.is_superuser:
        user.is_superuser = True
        updated = True
    if not user.is_active:
        user.is_active = True
        updated = True

    # Só redefina senha se você realmente quiser forçar isso no deploy.
    user.set_password(password)
    updated = True

    if updated:
        user.save()
        print(f"Superuser '{username}' already existed and was updated.")
    else:
        print(f"Superuser '{username}' already exists. No changes needed.")