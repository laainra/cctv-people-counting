import subprocess
import os

# Install requirements
subprocess.call('pip install -r requirements.txt', shell=True)

# Change directory to the Django project
os.chdir('Website')

# Run migrations and load initial data
subprocess.call('python manage.py migrate', shell=True)
# subprocess.call('python manage.py loaddata initial_data.json', shell=True)
subprocess.call('python manage.py create_superadmin', shell=True)
