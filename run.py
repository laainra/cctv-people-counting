import subprocess
import os

os.chdir('Website')

subprocess.call('start cmd /k "python manage.py runserver"', shell=True)

# subprocess.Popen("celery -A Website.celery worker --pool=solo -l info", shell=True)
# subprocess.Popen("celery -A Website.celery beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler", shell=True)

subprocess.call('start cmd /k "cd Dashboard/Artificial_Intelligence/ && python face_recognition_absence.py"', shell=True)