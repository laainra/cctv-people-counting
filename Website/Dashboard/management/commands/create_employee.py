from django.core.management.base import BaseCommand
from Dashboard.models import CustomUsers
from django.utils.crypto import get_random_string

class Command(BaseCommand):
    help = 'Create a employee with a default username and password'

    def handle(self, *args, **kwargs):
        username = 'employee'
        password = 'employee'
        role = 'employee'
        email = 'employee@gmail.com'
        
        # Check if the employee already exists
        if CustomUsers.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING('employee already exists'))
        else:
            # Create a employee and save the password with hashing
            user = CustomUsers.objects.create_user(username=username, password=password, email=email, role=role, is_employee=True)
            user.save()
            self.stdout.write(self.style.SUCCESS('Successfully created employee'))
