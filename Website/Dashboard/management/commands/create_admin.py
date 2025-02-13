from django.core.management.base import BaseCommand
from Dashboard.models import CustomUsers
from django.utils.crypto import get_random_string

class Command(BaseCommand):
    help = 'Create a admin with a default username and password'

    def handle(self, *args, **kwargs):
        username = 'admin123'
        password = 'admin123'
        role = 'admin'
        email = 'admin@gmail.com'
        
        # Check if the admin already exists
        if CustomUsers.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING('admin already exists'))
        else:
            # Create a admin and save the password with hashing
            user = CustomUsers.objects.create_user(username=username, password=password, email=email, role=role, is_admin=True)
            user.save()
            self.stdout.write(self.style.SUCCESS('Successfully created admin'))
