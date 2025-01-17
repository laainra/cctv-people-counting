from django.core.management.base import BaseCommand
from Dashboard.models import CustomUsers
from django.utils.crypto import get_random_string

class Command(BaseCommand):
    help = 'Create a superadmin with a default username and password'

    def handle(self, *args, **kwargs):
        username = 'superadmin'
        password = 'superadmin'
        role = 'superadmin'
        
        # Check if the superadmin already exists
        if CustomUsers.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING('superadmin already exists'))
        else:
            # Create a superadmin and save the password with hashing
            user = CustomUsers.objects.create_superuser(username=username, password=password,role=role, is_superadmin=True)
            user.save()
            self.stdout.write(self.style.SUCCESS('Successfully created superadmin'))
