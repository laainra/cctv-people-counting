from django.urls import path
from .views import presence, authentication, camera, home, personnel, settings
# from .views.presence import presence

urlpatterns = [
    path('', home.home, name="home"),
    path('login', authentication.user_login, name="login"),
    path('logout', authentication.user_logout, name="logout"),

    path('personnels', personnel.personnels, name="personnels"),
    path('add_personnel', personnel.add_personnel, name="add_personnel"),
    path('add_pic', personnel.add_pic, name="add_pic"),
    path('delete_personnel/<str:id>',
         personnel.delete_personnel, name="delete_personnel"),

    path('camera', camera.camera, name="camera"),
    path('video_feed', camera.video_feed, name='video_feed'),
    path('start_stream', camera.start_stream, name='start_stream'),
    path('add_camera', camera.add_camera, name="add_camera"),
    path('delete_camera/<str:id>', camera.delete_camera, name="delete_camera"),
    path('save_coordinates', camera.save_coordinates, name="save_coordinates"),
    path('stop_stream', camera.stop_stream, name="stop_stream"),
    path('change_camera', camera.change_camera, name="change_camera"),
    path('edit_camera/<str:id>', camera.edit_camera, name="edit_camera"),
    path('edit_personnel', personnel.edit_personnel, name="edit_personnel"),
    path('settings', settings.settings, name="settings"),
    path('presence', presence.presence, name="presence"),
    path('download', home.download, name="download"),

]
