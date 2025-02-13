from django.apps import AppConfig
from threading import Thread

class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Dashboard'

    def ready(self):
        # Start the presence watching thread
        from .views.presence import start_watching 
        thread_watching = Thread(target=start_watching)
        thread_watching.daemon = True  # Make the thread exit when the main program exits
        thread_watching.start()

        # Start the work timer thread
        from .views.work_timer import work_timer
        thread_work_timer = Thread(target=work_timer)
        thread_work_timer.daemon = True  # Make the thread exit when the main program exits
        thread_work_timer.start()
