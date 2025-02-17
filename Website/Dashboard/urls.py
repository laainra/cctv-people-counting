from django.urls import path
from .views import face_rec, profile, presence, authentication, camera, home, personnel, settings, superadmin, stream, admin, employee, work_timer, tracking
# from .views.presence import presence

urlpatterns = [
    path('', admin.admin_home, name='home'),
    path('login', authentication.user_login, name="login"),
    path('logout', authentication.user_logout, name="logout"),

    path('personnels', personnel.personnels, name="personnels"),
    path('add_personnel/', personnel.add_personnel, name="add_personnel"),
    path('add_pic', personnel.add_pic, name="add_pic"),
    path('delete_personnel/<str:id>',
         personnel.delete_personnel, name="delete_personnel"),

    path('camera', camera.camera, name="camera"),
    path('video_feed', camera.video_feed, name='video_feed'),
    path('start_stream/', camera.start_stream, name='start_stream'),
    path('stop_stream/', camera.start_stream, name='stop_stream'),
    path('add_camera', camera.add_camera, name="add_camera"),
    path('add_tracking_camera/', camera.add_tracking_camera, name='add_tracking_camera'),
    path('add_presence_camera/', camera.add_presence_camera, name='add_presence_camera'),
    path('edit_tracking_camera/<str:id>/', camera.edit_tracking_camera, name='edit_tracking_camera'),
     path('edit_presence_camera/<str:id>/',camera.edit_presence_camera, name='edit_presence_camera'),
     path('get_edit_camera_url/<str:id>/', camera.get_edit_camera_url, name='get_edit_camera_url'),
     path('get_camera_data/<str:id>/', camera.get_camera_data, name='get_camera_data'),
    # path('get_tracking_camera/<int:camera_id>/', camera.get_tracking_camera, name='get_tracking_camera'),
    path('delete_camera/<int:id>/', camera.delete_camera, name="delete_camera"),
    path('save_coordinates', camera.save_coordinates, name="save_coordinates"),
    path('change_camera', camera.change_camera, name="change_camera"),
    path('edit_camera/<str:id>', camera.edit_camera, name="edit_camera"),
    path('edit_personnel', personnel.edit_personnel, name="edit_personnel"),
    path('personnel-entries', personnel.personnel_entries_data, name='personnel_entries_data'),
    path('download_personnel_presence', personnel.download_personnel_presence, name='download_personnel_presence'),
    path('settings', settings.settings, name="settings"),
    path('presence/', presence.presence, name="presence"),
    path('download_presence_excel', presence.download_presence_excel, name="download_presence_excel"),
    path('download', home.download, name="download"),
    # path('personnels/add', personnel.add_personnel, name='add_personnel'),
    path('personnels/<int:personnel_id>/', personnel.get_personnel, name='get_personnel'),
    path('personnels/edit/<int:personnel_id>/', personnel.edit_personnel, name='edit_personnel'),
    path('personnels/delete/<int:personnel_id>/', personnel.delete_personnel, name='delete_personnel'),
    path('personnels/attendance/<int:personnel_id>/', personnel.attendance_details, name='attendance_details'),
    path('personnels/images/<int:personnel_id>/', personnel.get_personnel_images, name='personnel_images'),
    path('personnels/images/add/<int:personnel_id>/', personnel.add_personnel_image, name='add_personnel_image'),
    path('personnels/images/delete/<int:image_id>/', personnel.delete_personnel_image, name='delete_personnel_image'),
    path('personnels/images/move/<int:image_id>/', personnel.move_personnel_image, name='move_personnel_image'),
    
    path('superadmin/', superadmin.superadmin_home, name='superadmin_home'),
    path('superadmin/company/', superadmin.company, name='company'),
    path('superadmin/company/<int:company_id>/', superadmin.get_company, name='get_company'),
    path('superadmin/company/add/', superadmin.add_company, name='add_company'),
    path('superadmin/company/edit/<int:company_id>/', superadmin.edit_company, name='edit_company'),
    path('superadmin/company/delete/<int:company_id>/', superadmin.delete_company, name='delete_company'),
    path('dashboard/', admin.admin_home, name='admin_home'),
    path('divisions/', admin.division, name='divisions'),
    path('add_division/', admin.add_division, name='add_division'),
    path('get_divisions/', admin.get_divisions, name='get_divisions'),
    path('get_division/<int:id>/', admin.get_division, name='get_division'),
    path('edit_division/<int:id>/', admin.edit_division, name='edit_division'),
    path('delete_division/<int:id>/', admin.delete_division, name='delete_division'),
    path('employees/', admin.employees, name='employees'),
    # path('presence/', admin.presence, name='presence'),
    path('presence_cam/', admin.presence_cam, name='presence_cam'),
    path('tracking_cam/', admin.tracking_cam, name='tracking_cam'),

    path('employee/', employee.employee_home, name='employee_home'),
    path('employee/presence_history/', employee.presence_history, name='presence_history'),
    path('employee/take_image/', employee.take_image, name='take_image'),

    # URL lainnya...
    path('start_ai_stream/', stream.start_ai_stream, name='start_ai_stream'),
    path('stop_ai_stream/', stream.stop_ai_stream, name='stop_ai_stream'),
    path('ai_video_feed/', stream.ai_video_feed, name='ai_video_feed'),
    path('set_cam_id/', stream.set_cam_id, name='set_cam_id'),
    path('stream/', stream.stream, name='stream'),
    path('presence_stream/', stream.presence_stream, name='presence_stream'),
    path('tracking_stream/', stream.tracking_stream, name='tracking_stream'),
    
    path('profile/', profile.profile, name='profile'),

    path('capture/', face_rec.capture_page, name='capture_page'),
    path('capture_data/', face_rec.capture_faces, name='capture_faces'),
    path('capture_video/', face_rec.capture_video, name='capture_video'),
    path('train/', face_rec.train_model, name='train_model'),
    path('recognize/', face_rec.predict_video, name='predict_video'),
    path('dataset/', face_rec.dataset, name='dataset'),
    
    path('work_time_report/', work_timer.work_time_report, name='work_time_report'),
    path('video_feed_timer/<int:cam_id>/', work_timer.video_feed_timer, name='video_feed_timer'),
    
    path('tracking_report/', tracking.tracking_report, name='tracking_report'),
]