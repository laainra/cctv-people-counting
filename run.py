import subprocess
import os

os.chdir('Website')

subprocess.Popen("python manage.py runserver 0.0.0.0:8000", shell=True)

subprocess.Popen("celery -A Website.celery worker --pool=solo -l info", shell=True)
subprocess.Popen("celery -A Website.celery beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler", shell=True)