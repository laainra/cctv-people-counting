import os
from django.conf import settings


class var:
    personnel_path = os.path.join(
        settings.BASE_DIR, 'dashboard', 'static', 'img', 'personnel_pics')
    report_path = os.path.join(settings.BASE_DIR, 'dashboard', 'static')
    presence_path = os.path.join(settings.BASE_DIR, 'dashboard', 'static', 'img', 'presence_folder')
