import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tailor_management_system.settings')
django.setup()

from dashboard.models import reception_login

def setup_reception():
    username = 'reception'
    password = 'password123'
    
    users = reception_login.objects.all()
    if users.exists():
        print("Existing Reception Users:")
        for user in users:
            print(f"Username: {user.user_name} | Password: {user.password}")
    else:
        print(f"No reception users found. Creating '{username}'.")
        reception_login.objects.create(user_name=username, password=password)
        print(f"Created Reception User:\nUsername: {username}\nPassword: {password}")

if __name__ == '__main__':
    setup_reception()