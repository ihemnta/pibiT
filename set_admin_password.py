#!/usr/bin/env python3
"""
Script to set admin password for Django admin panel
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ticketing_service.settings')
django.setup()

from django.contrib.auth.models import User
from decouple import config

def set_admin_password():
    """Set or create admin user with password from environment"""
    admin_username = config('ADMIN_USERNAME', default='admin')
    admin_email = config('ADMIN_EMAIL', default='admin@example.com')
    admin_password = config('ADMIN_PASSWORD', default='admin')
    
    try:
        # Try to get existing admin user
        admin_user = User.objects.get(username=admin_username)
        print(f"✅ Found existing admin user: {admin_username}")
    except User.DoesNotExist:
        # Create new admin user
        admin_user = User.objects.create_superuser(
            username=admin_username,
            email=admin_email,
            password=admin_password
        )
        print(f"✅ Created new admin user: {admin_username}")
    
    # Set password
    admin_user.set_password(admin_password)
    admin_user.save()
    
    print(f"✅ Admin password set successfully!")
    print(f"   Username: {admin_username}")
    print(f"   Email: {admin_email}")
    print(f"   Password: {admin_password}")
    print(f"\n🔗 Admin URL: http://localhost:8000/admin/")

if __name__ == "__main__":
    set_admin_password()
