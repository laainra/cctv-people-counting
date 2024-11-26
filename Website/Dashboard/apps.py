from django.apps import AppConfig
from threading import Thread

class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Dashboard'

    def ready(self):
        from .views.presence import start_watching 
        thread = Thread(target=start_watching)
        thread.daemon = True  # Make the thread exit when the main program exits
        thread.start()
