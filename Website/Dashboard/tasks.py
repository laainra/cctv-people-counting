from celery import shared_task
from . import models
import os, shutil
from datetime import datetime
from .views.var import var

@shared_task(bind=True)
def deleteUnknownEveryDay(self):
    folder = os.path.join(var.personnel_path, 'Unknown')
    now = datetime.now().date()
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try: 
            f = open(os.path.join(os.path.dirname(__file__), 'static', 'unknown_deletion.txt'), "r")
            deletion_time = int(f.read())

            file_date, _ = filename.split('_')
            file_year, file_month, file_day = file_date.split('-')
            file_date = datetime(year=int(file_year), month=int(file_month), day=int(file_day)).date()
            dif = now - file_date
            if(dif.days > deletion_time):
                os.unlink(file_path)
        except ValueError:
            pass

    return "Succeed deleting old unknown pics at "+ datetime.now()