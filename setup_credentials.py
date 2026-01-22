import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tailor_management_system.settings')
django.setup()

from dashboard.models import admin_login, AddTailors

def setup_admin():
    username = 'admin'
    password = 'password123'
    
    if admin_login.objects.filter(username=username).exists():
        print(f"Admin user '{username}' already exists. Updating password.")
        admin = admin_login.objects.get(username=username)
        admin.password = password
        admin.save()
    else:
        print(f"Creating new admin user '{username}'.")
        admin_login.objects.create(username=username, password=password)
    
    print(f"Admin Credentails:\nUsername: {username}\nPassword: {password}\n")

def list_tailors():
    tailors = AddTailors.objects.all()
    print("Tailor Credentials (from database):")
    if not tailors:
        print("No tailors found.")
        return

    for tailor in tailors:
        print(f"Tailor: {tailor.tailor} | Username: {tailor.username} | Password: {tailor.password} | Mobile: {tailor.mobile_number}")

if __name__ == '__main__':
    setup_admin()
    list_tailors()
