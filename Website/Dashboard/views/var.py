import os
from django.conf import settings

class var:
    personnel_path = os.path.join(settings.BASE_DIR, 'dashboard', 'static', 'img', 'personnel_pics')
