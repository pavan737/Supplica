#!/usr/bin/env python
"""
Create a superuser for the admin panel if one doesn't exist.
Usage: python manage.py shell < create_superuser.py
"""

from django.contrib.auth.models import User

# Check existing users
users = User.objects.all()
print(f"Total users: {users.count()}")
for u in users:
    print(f"  - {u.username} (email: {u.email}, is_superuser: {u.is_superuser})")

# Check if superuser exists
superusers = User.objects.filter(is_superuser=True)
if superusers.count() == 0:
    print("\nNo superuser found. Creating one...")
    User.objects.create_superuser(
        username='admin',
        email='admin@supplica.com',
        password='Admin@123'
    )
    print("✓ Superuser created!")
    print("  Username: admin")
    print("  Email: admin@supplica.com")
    print("  Password: Admin@123")
else:
    print(f"\n✓ Superuser already exists: {superusers.first().username}")
