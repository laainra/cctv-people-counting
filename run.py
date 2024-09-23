import subprocess
import os

os.chdir('Website')

subprocess.call('start cmd /k "py manage.py runserver"', shell=True)
subprocess.call('start cmd /k "celery -A Website.celery worker --pool=solo -l info"', shell=True)
subprocess.call('start cmd /k "celery -A Website.celery beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler"', shell=True)