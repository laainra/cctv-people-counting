from django.apps import AppConfig
from threading import Thread

class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Dashboard'

    def ready(self):
        
        # Start the work timer thread
        # from .views.face_rec import recognize_face
        # thread_work_timer = Thread(target=recognize_face)
        # thread_work_timer.daemon = True
        # thread_work_timer.start()
        
        # Start the presence watching thread
        from .views.presence import start_watching 
        thread_watching = Thread(target=start_watching)
        thread_watching.daemon = True 
        thread_watching.start()

