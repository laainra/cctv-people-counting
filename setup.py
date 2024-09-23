import subprocess
import os

subprocess.call('pip install -r requirements.txt', shell=True)

os.chdir('Website')

subprocess.call('py manage.py migrate', shell=True)
subprocess.call('py manage.py loaddata initial_data.json', shell=True)